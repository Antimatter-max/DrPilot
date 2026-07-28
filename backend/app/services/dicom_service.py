import os
import uuid
import pydicom
from fastapi import UploadFile

VNA_STORAGE_DIR = "/app/vna_storage"
os.makedirs(VNA_STORAGE_DIR, exist_ok=True)

def process_and_store_dicom(file: UploadFile) -> dict:
    """
    Saves DICOM to VNA storage, strips PHI metadata, 
    and returns parsed metadata.
    """
    # Generate unique filename for VNA storage
    file_extension = ".dcm"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    save_path = os.path.join(VNA_STORAGE_DIR, unique_filename)

    # Save incoming file to VNA disk
    with open(save_path, "wb") as buffer:
        buffer.write(file.file.read())

    # Read DICOM headers
    ds = pydicom.dcmread(save_path, force=True)

    # Extract required fields with fallbacks
    patient_uid = getattr(ds, "PatientID", "ANON_PATIENT")
    sop_instance_uid = getattr(ds, "SOPInstanceUID", str(uuid.uuid4()))
    series_instance_uid = getattr(ds, "SeriesInstanceUID", None)
    modality = getattr(ds, "Modality", "UNKNOWN")
    body_part = getattr(ds, "BodyPartExamined", "UNSPECIFIED")
    gender = getattr(ds, "PatientSex", "U")

    # Optional Age parsing
    age_str = getattr(ds, "PatientAge", None)
    age = None
    if age_str and age_str[:-1].isdigit():
        age = int(age_str[:-1])

    return {
        "patient_uid": str(patient_uid),
        "sop_instance_uid": str(sop_instance_uid),
        "series_instance_uid": str(series_instance_uid) if series_instance_uid else None,
        "modality": str(modality),
        "body_part_examined": str(body_part),
        "gender": str(gender),
        "age": age,
        "file_path": save_path
    }