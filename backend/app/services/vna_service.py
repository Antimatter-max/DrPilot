import os
import pydicom
from datetime import datetime
from typing import Dict, Any, List

VNA_STORAGE_DIR = os.getenv("VNA_STORAGE_DIR", "/app/vna_storage")


def scan_patient_vna_directory(patient_uid: str) -> Dict[str, Any]:
    """
    Scans vna_storage/{patient_uid}/ for real DICOM scans and text notes on disk.
    Does NOT create synthetic mock data. Returns 404 if directory does not exist.
    """
    patient_dir = os.path.join(VNA_STORAGE_DIR, patient_uid)

    if not os.path.exists(patient_dir) or not os.path.isdir(patient_dir):
        return None

    dicom_dir = os.path.join(patient_dir, "dicom")
    notes_dir = os.path.join(patient_dir, "notes")

    imaging_studies = []
    patient_metadata = {
        "patient_id": patient_uid,
        "age": "N/A",
        "gender": "N/A",
    }

    # 1. Read DICOM files from disk
    if os.path.exists(dicom_dir):
        for filename in os.listdir(dicom_dir):
            if filename.lower().endswith(('.dcm', '.dicom')):
                filepath = os.path.join(dicom_dir, filename)
                try:
                    ds = pydicom.dcmread(filepath, stop_before_pixels=True, force=True)
                    
                    # Extract patient demographics from DICOM header if available
                    if hasattr(ds, "PatientSex") and ds.PatientSex:
                        patient_metadata["gender"] = str(ds.PatientSex)
                    if hasattr(ds, "PatientAge") and ds.PatientAge:
                        patient_metadata["age"] = str(ds.PatientAge)

                    modality = getattr(ds, "Modality", "UNKNOWN")
                    body_part = getattr(ds, "BodyPartExamined", "UNSPECIFIED")
                    study_date = getattr(ds, "StudyDate", None)
                    
                    # Format study date if available
                    formatted_date = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%B %d, %Y - %H:%M")
                    if study_date and len(study_date) == 8:
                        formatted_date = f"{study_date[:4]}-{study_date[4:6]}-{study_date[6:]}"

                    imaging_studies.append({
                        "file_name": filename,
                        "modality": str(modality),
                        "body_part": str(body_part),
                        "date": formatted_date,
                        "file_path": filepath,
                        "sop_instance_uid": str(getattr(ds, "SOPInstanceUID", filename))
                    })
                except Exception as e:
                    print(f"Error reading DICOM {filename}: {e}")

    # 2. Read Clinical Notes & Logs from disk
    clinical_timeline = []
    if os.path.exists(notes_dir):
        for filename in os.listdir(notes_dir):
            if filename.lower().endswith(('.txt', '.log', '.json')):
                filepath = os.path.join(notes_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        raw_text = f.read()

                    category = "Clinical Note"
                    title = filename.replace(".txt", "").replace("_", " ").title()
                    content = raw_text

                    # Basic parsing if "Category:" or "Title:" headers exist in the .txt file
                    if "---" in raw_text:
                        header_part, content_part = raw_text.split("---", 1)
                        content = content_part.strip()
                        for line in header_part.splitlines():
                            if line.lower().startswith("category:"):
                                category = line.split(":", 1)[1].strip()
                            elif line.lower().startswith("title:"):
                                title = line.split(":", 1)[1].strip()

                    file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%B %d, %Y - %H:%M")

                    clinical_timeline.append({
                        "file_name": filename,
                        "category": category,
                        "title": title,
                        "content": content,
                        "timestamp": file_mtime
                    })
                except Exception as e:
                    print(f"Error reading note file {filename}: {e}")

    return {
        "patient_info": patient_metadata,
        "imaging_studies": imaging_studies,
        "clinical_timeline": clinical_timeline
    }