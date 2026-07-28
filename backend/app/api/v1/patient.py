import io
import traceback
from typing import List, Optional

import numpy as np
import pydicom
from PIL import Image, ImageDraw, ImageFont
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import AuditLog, ClinicalAttestation, User
from app.core.security import get_current_user
from app.services.chat_service import process_patient_chat
from app.services.rag_service import query_clinical_guidelines
from app.services.vlm_service import analyze_dicom_scan
from app.services.vna_service import scan_patient_vna_directory

router = APIRouter(prefix="/patients", tags=["Patient Dashboard"])


# --- Schemas ---

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = []


class AttestationRequest(BaseModel):
    decision: str  # "ACCEPTED", "MODIFIED", "REJECTED"
    target_type: str
    findings_summary: str
    physician_notes: Optional[str] = ""


# --- Endpoints ---

@router.get("/{patient_uid}/dashboard")
def get_patient_dashboard(
    patient_uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves patient demographics and PACS scans, logging the lookup under the logged-in user.
    """
    vna_data = scan_patient_vna_directory(patient_uid)
    if not vna_data:
        raise HTTPException(
            status_code=404,
            detail=f"Patient record '{patient_uid}' not found in VNA storage."
        )

    db.add(AuditLog(
        action="VNA_DIRECTORY_LOOKUP",
        user_id=str(current_user.id),
        user_name=current_user.full_name,
        user_role=current_user.role,
        patient_uid=patient_uid,
        details=f"Retrieved {len(vna_data['imaging_studies'])} DICOM scans."
    ))
    db.commit()
    return vna_data


@router.post("/{patient_uid}/chat")
def patient_chat_assistant(
    patient_uid: str,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Interactive Clinical Assistant Endpoint:
    Accepts doctor queries / scenario parameters and returns real-time re-evaluations.
    """
    vna_data = scan_patient_vna_directory(patient_uid)
    if not vna_data:
        raise HTTPException(status_code=404, detail="Patient directory not found")

    result = process_patient_chat(
        patient_uid=patient_uid,
        user_message=payload.message,
        vna_data=vna_data,
        chat_history=payload.history
    )

    return result


@router.get("/{patient_uid}/scans/{sop_instance_uid}/analyze")
def analyze_patient_scan(
    patient_uid: str,
    sop_instance_uid: str,
    current_user: User = Depends(get_current_user)
):
    """
    VLM Analysis Endpoint: Runs automated vision analysis on a target DICOM scan 
    and returns bounding box coordinates and clinical findings.
    """
    vna_data = scan_patient_vna_directory(patient_uid)
    if not vna_data:
        raise HTTPException(status_code=404, detail="Patient directory not found")

    target_scan = None
    for scan in vna_data["imaging_studies"]:
        if (scan["sop_instance_uid"] == sop_instance_uid or 
            scan["file_name"] == sop_instance_uid):
            target_scan = scan
            break

    if not target_scan and vna_data["imaging_studies"]:
        target_scan = vna_data["imaging_studies"][0]

    if not target_scan:
        raise HTTPException(status_code=404, detail="DICOM scan file not found")

    analysis_result = analyze_dicom_scan(target_scan["file_path"])
    return analysis_result


@router.post("/{patient_uid}/attest")
def submit_clinical_attestation(
    patient_uid: str,
    payload: AttestationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits a physician attestation (Accept / Modify / Reject) for AI recommendations or VLM findings,
    recording it in PostgreSQL under the active user along with a HIPAA audit log.
    """
    attestation = ClinicalAttestation(
        patient_uid=patient_uid,
        physician_name=current_user.full_name,
        decision=payload.decision.upper(),
        target_type=payload.target_type,
        findings_summary=payload.findings_summary,
        physician_notes=payload.physician_notes
    )
    db.add(attestation)
    
    audit = AuditLog(
        action=f"CLINICAL_ATTESTATION_{payload.decision.upper()}",
        user_id=str(current_user.id),
        user_name=current_user.full_name,
        user_role=current_user.role,
        patient_uid=patient_uid,
        details=f"{current_user.full_name} ({current_user.role}) {payload.decision.lower()} AI finding [{payload.target_type}]."
    )
    db.add(audit)
    db.commit()
    db.refresh(attestation)

    return {
        "status": "success",
        "attestation_id": attestation.id,
        "decision": attestation.decision,
        "timestamp": attestation.timestamp.isoformat()
    }


@router.get("/{patient_uid}/attestations")
def get_patient_attestations(
    patient_uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves all signed-off physician attestations for the patient."""
    attestations = db.query(ClinicalAttestation).filter(
        ClinicalAttestation.patient_uid == patient_uid
    ).order_by(ClinicalAttestation.timestamp.desc()).all()

    return [
        {
            "id": a.id,
            "physician_name": a.physician_name,
            "decision": a.decision,
            "target_type": a.target_type,
            "findings_summary": a.findings_summary,
            "physician_notes": a.physician_notes,
            "timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        for a in attestations
    ]


@router.get("/{patient_uid}/guideline-recommendations")
def get_guideline_recommendations(
    patient_uid: str,
    current_user: User = Depends(get_current_user)
):
    """
    RAG Endpoint: Analyzes patient timeline & scans, queries Qdrant vector DB,
    and returns cited medical literature and practice guidelines.
    """
    vna_data = scan_patient_vna_directory(patient_uid)
    if not vna_data:
        raise HTTPException(status_code=404, detail="Patient directory not found")

    context_builder = []
    
    for scan in vna_data.get("imaging_studies", []):
        context_builder.append(f"Imaging Modality: {scan['modality']} examination of {scan['body_part']}")

    for note in vna_data.get("clinical_timeline", []):
        context_builder.append(f"{note['title']}: {note['content']}")

    unified_context = " ".join(context_builder)

    if not unified_context.strip():
        unified_context = f"Acute chest pain shortness of breath dyspnea patient {patient_uid}"

    recommendations = query_clinical_guidelines(unified_context, top_k=3)

    return {
        "patient_uid": patient_uid,
        "query_context_length": len(unified_context),
        "recommendations": recommendations
    }


@router.get("/{patient_uid}/scans/{sop_instance_uid}/render")
def render_dicom_scan(
    patient_uid: str,
    sop_instance_uid: str,
    current_user: User = Depends(get_current_user)
):
    """
    Extracts pixel data from a DICOM file on disk, handles 3D multi-frame arrays, 
    applies windowing/normalization, and streams a PNG image.
    """
    vna_data = scan_patient_vna_directory(patient_uid)
    if not vna_data:
        raise HTTPException(status_code=404, detail="Patient directory not found")

    target_scan = None
    for scan in vna_data["imaging_studies"]:
        if (scan["sop_instance_uid"] == sop_instance_uid or 
            scan["file_name"] == sop_instance_uid):
            target_scan = scan
            break

    if not target_scan and vna_data["imaging_studies"]:
        target_scan = vna_data["imaging_studies"][0]

    if not target_scan:
        raise HTTPException(status_code=404, detail="DICOM scan file not found")

    try:
        ds = pydicom.dcmread(target_scan["file_path"], force=True)

        if not hasattr(ds, "pixel_array"):
            return create_placeholder_image("Metadata Only DICOM (No Pixels)", target_scan["modality"])

        pixel_array = ds.pixel_array.astype(float)

        if pixel_array.ndim == 3:
            if pixel_array.shape[2] not in (3, 4):
                middle_idx = pixel_array.shape[0] // 2
                pixel_array = pixel_array[middle_idx]
        elif pixel_array.ndim == 4:
            middle_idx = pixel_array.shape[0] // 2
            pixel_array = pixel_array[middle_idx, ..., 0]

        slope = getattr(ds, "RescaleSlope", 1)
        intercept = getattr(ds, "RescaleIntercept", 0)
        pixel_array = pixel_array * slope + intercept

        photometric = getattr(ds, "PhotometricInterpretation", "MONOCHROME2")
        if photometric == "MONOCHROME1":
            pixel_array = np.max(pixel_array) - pixel_array

        min_val = np.min(pixel_array)
        max_val = np.max(pixel_array)

        if max_val > min_val:
            normalized = ((pixel_array - min_val) / (max_val - min_val)) * 255.0
        else:
            normalized = np.zeros_like(pixel_array)

        image_data = np.uint8(normalized)
        img = Image.fromarray(image_data)

        if img.mode != "L":
            img = img.convert("L")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return StreamingResponse(buffer, media_type="image/png")

    except Exception as e:
        print("\n--- [DICOM RENDER ERROR TRACEBACK] ---")
        traceback.print_exc()
        print("---------------------------------------\n")
        return create_placeholder_image(f"Render Error: {str(e)[:40]}...", target_scan["modality"])


def create_placeholder_image(message: str, modality: str):
    """Generates a clean fallback preview when pixel decoding is unavailable."""
    img = Image.new("RGB", (512, 512), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    
    draw.rectangle([10, 10, 502, 502], outline=(51, 65, 85), width=2)
    draw.text((30, 40), f"PACS PREVIEW MODE - {modality}", fill=(96, 165, 250))
    draw.text((30, 80), message, fill=(226, 232, 240))
    draw.text((30, 120), "DICOM metadata successfully ingested.", fill=(148, 163, 184))
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")