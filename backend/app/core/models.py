from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class IngestedDocument(Base):
    __tablename__ = "ingested_documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), unique=True, index=True, nullable=False) # SHA-256
    file_size_bytes = Column(Integer, nullable=False)
    status = Column(String(50), default="PENDING") # PENDING, PROCESSING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    chunks_count = Column(Integer, default=0)
    category = Column(String(100), default="General Guideline")
    created_at = Column(DateTime, default=datetime.utcnow)

class PatientRecord(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_uid = Column(String, unique=True, index=True, nullable=False)  # Anonymized / ID
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships (One Patient -> Multiple Scans & Notes)
    scans = relationship("DicomScan", back_populates="patient", cascade="all, delete-orphan")
    notes = relationship("ClinicalNote", back_populates="patient", cascade="all, delete-orphan")


class DicomScan(Base):
    __tablename__ = "dicom_scans"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    sop_instance_uid = Column(String, unique=True, index=True, nullable=False)
    series_instance_uid = Column(String, index=True, nullable=True)
    modality = Column(String, nullable=False)  # e.g., CT, DX, CR, MR
    body_part_examined = Column(String, nullable=True)
    file_path = Column(String, nullable=False)  # Path in VNA/Storage
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("PatientRecord", back_populates="scans")


class ClinicalNote(Base):
    __tablename__ = "clinical_notes"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    note_type = Column(String, nullable=False)  # e.g., "physician_note", "surgical_preop", "lab_result"
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("PatientRecord", back_populates="notes")


import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)  # PHYSICIAN, CMO_GOVERNANCE, SURGEON
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(100), nullable=False)
    user_id = Column(String(100), default="USR-8842")
    user_name = Column(String(100), default="Dr. Alex Vance")
    user_role = Column(String(50), default="PHYSICIAN")
    patient_uid = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), default="127.0.0.1")
    compliance_flag = Column(String(50), default="HIPAA_COMPLIANT")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


class ClinicalAttestation(Base):
    __tablename__ = "clinical_attestations"

    id = Column(Integer, primary_key=True, index=True)
    patient_uid = Column(String(50), nullable=False)
    physician_id = Column(String(100), default="DR-8842")
    physician_name = Column(String(100), default="Dr. Alex Vance, MD")
    user_role = Column(String(50), default="PHYSICIAN")
    decision = Column(String(50), nullable=False)
    target_type = Column(String(50), nullable=False)
    findings_summary = Column(Text, nullable=False)
    physician_notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

