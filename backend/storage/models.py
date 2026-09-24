import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Enum as SAEnum,
    Uuid,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship

from storage.base import Base


# Helper for JSONB on PostgreSQL and JSON on others
JSONType = JSON().with_variant(JSONB, "postgresql")
UUIDType = Uuid(as_uuid=True).with_variant(PG_UUID(as_uuid=True), "postgresql")
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Enums matching database.md schemas exactly
class StationStatus(str, enum.Enum):
    active = "active"
    maintenance = "maintenance"
    decommissioned = "decommissioned"


class QCVerdict(str, enum.Enum):
    valid = "valid"
    suspect = "suspect"
    anomalous = "anomalous"


class AlertSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class FeedbackLabel(str, enum.Enum):
    confirmed_fault = "confirmed_fault"
    false_alarm = "false_alarm"
    unsure = "unsure"


class UserRole(str, enum.Enum):
    admin = "admin"
    forecaster = "forecaster"
    qc_analyst = "qc_analyst"
    data_quality_officer = "data_quality_officer"
    field_technician = "field_technician"
    viewer = "viewer"


class Station(Base):
    """Metadata registry for every AWS station."""
    __tablename__ = "stations"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    station_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation_m = Column(Float, nullable=True)
    state = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    install_date = Column(Date, nullable=True)
    sensor_specs = Column(JSONType, nullable=False, default=dict)
    status = Column(
        SAEnum(StationStatus, name="station_status"),
        nullable=False,
        default=StationStatus.active,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    readings = relationship("RawReading", back_populates="station", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="station", cascade="all, delete-orphan")
    predictions = relationship("MaintenancePrediction", back_populates="station", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_stations_lat_lon", "latitude", "longitude"),
    )


class RawReading(Base):
    """Raw sensor readings streamed from stations or simulator."""
    __tablename__ = "raw_readings"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    station_id = Column(UUIDType, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    temperature = Column(Float, nullable=True)  # °C
    humidity = Column(Float, nullable=True)     # %
    pressure = Column(Float, nullable=True)     # hPa
    wind_speed = Column(Float, nullable=True)   # m/s
    wind_direction = Column(Float, nullable=True)  # degrees
    rainfall = Column(Float, nullable=True)     # mm
    solar_radiation = Column(Float, nullable=True)  # W/m²
    ingest_source = Column(String(50), nullable=False, default="simulator")
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    station = relationship("Station", back_populates="readings")
    qc_results = relationship("QCResult", back_populates="reading", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("station_id", "timestamp", name="uq_station_timestamp"),
        Index("idx_raw_readings_station_time", "station_id", "timestamp"),
    )


class QCResult(Base):
    """Quality control verdicts produced by the multi-layer pipeline."""
    __tablename__ = "qc_results"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    reading_id = Column(BigInteger, ForeignKey("raw_readings.id", ondelete="CASCADE"), nullable=False, index=True)
    station_id = Column(UUIDType, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    variable = Column(String(50), nullable=False)
    verdict = Column(SAEnum(QCVerdict, name="qc_verdict"), nullable=False, index=True)
    reason_code = Column(String(50), nullable=False)
    fault_type = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=False)
    ml_model_version = Column(String(50), nullable=True)
    details = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    reading = relationship("RawReading", back_populates="qc_results")
    station = relationship("Station")
    alerts = relationship("Alert", back_populates="qc_result", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="qc_result", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_qc_results_station_created", "station_id", "created_at"),
        Index("idx_qc_results_verdict", "verdict"),
    )


class Alert(Base):
    """Operational alerts generated when anomalous verdicts exceed severity threshold."""
    __tablename__ = "alerts"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    station_id = Column(UUIDType, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    qc_result_id = Column(BigInteger, ForeignKey("qc_results.id", ondelete="CASCADE"), nullable=False, index=True)
    severity = Column(SAEnum(AlertSeverity, name="alert_severity"), nullable=False)
    status = Column(SAEnum(AlertStatus, name="alert_status"), nullable=False, default=AlertStatus.open)
    message = Column(Text, nullable=False)
    channel_sent = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    station = relationship("Station", back_populates="alerts")
    qc_result = relationship("QCResult", back_populates="alerts")


class Feedback(Base):
    """Operator ground-truth feedback for continuous retraining."""
    __tablename__ = "feedback"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    qc_result_id = Column(BigInteger, ForeignKey("qc_results.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUIDType, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    label = Column(SAEnum(FeedbackLabel, name="feedback_label"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    qc_result = relationship("QCResult", back_populates="feedback")
    user = relationship("User", back_populates="feedbacks")


class User(Base):
    """System operators and personnel with role-based access."""
    __tablename__ = "users"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(SAEnum(UserRole, name="user_role"), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    feedbacks = relationship("Feedback", back_populates="user")


class ModelRegistry(Base):
    """Trained machine-learning model audit log and registry."""
    __tablename__ = "model_registry"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    model_type = Column(String(50), nullable=False)  # isolation_forest / lstm_autoencoder
    variable = Column(String(50), nullable=False)
    version = Column(String(50), nullable=False)
    trained_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    training_data_range = Column(String(100), nullable=True)
    metrics = Column(JSONType, nullable=False, default=dict)
    artifact_path = Column(String(500), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)


class MaintenancePrediction(Base):
    """Predictive maintenance risk scores per station."""
    __tablename__ = "maintenance_predictions"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    station_id = Column(UUIDType, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    predicted_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    failure_probability_30d = Column(Float, nullable=False)
    top_factors = Column(JSONType, nullable=False, default=dict)

    # Relationships
    station = relationship("Station", back_populates="predictions")


class SystemTask(Base):
    """Operational, maintenance, and QC tasks partitioned by RBAC role."""
    __tablename__ = "system_tasks"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    assigned_role = Column(String(50), nullable=False, index=True)
    priority = Column(String(50), nullable=False, default="medium")
    status = Column(String(50), nullable=False, default="pending", index=True)
    category = Column(String(50), nullable=False, default="general")
    station_code = Column(String(50), nullable=True, index=True)
    assigned_to_name = Column(String(255), nullable=True)
    due_date = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class Role(Base):
    """System RBAC Role definition."""
    __tablename__ = "roles"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")


class Permission(Base):
    """Granular operational permission code."""
    __tablename__ = "permissions"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    code = Column(String(100), unique=True, nullable=False, index=True)
    module = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    roles = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")


class RolePermission(Base):
    """Many-to-many relationship mapping Roles to Permissions."""
    __tablename__ = "role_permissions"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    role_id = Column(UUIDType, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id = Column(UUIDType, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)

    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )


class AuditLog(Base):
    """Security, administrative, and data access audit trail."""
    __tablename__ = "audit_logs"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    user_id = Column(UUIDType, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email = Column(String(255), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource = Column(String(100), nullable=False)
    details = Column(JSONType, nullable=False, default=dict)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class SystemSetting(Base):
    """Dynamic operational configuration and ML pipeline hyperparameters."""
    __tablename__ = "system_settings"

    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSONType, nullable=False, default=dict)
    description = Column(Text, nullable=True)
    updated_by = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

