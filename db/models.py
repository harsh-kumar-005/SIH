"""
db/models.py
============
SQLAlchemy ORM models implementing the core database schema:
  - users
  - circuits
  - simulation_runs (append-only)
  - predictions
"""

import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    SmallInteger,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    CheckConstraint,
    func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    role = Column(
        Text,
        CheckConstraint("role IN ('student', 'instructor')", name="check_user_role"),
        nullable=False,
        default="student"
    )
    display_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    circuits = relationship("Circuit", back_populates="owner")
    predictions = relationship("Prediction", back_populates="user")
    concept_masteries = relationship("ConceptMastery", back_populates="user", cascade="all, delete-orphan")
    misconception_events = relationship("MisconceptionEvent", back_populates="user", cascade="all, delete-orphan")


class Circuit(Base):
    __tablename__ = "circuits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    qubit_count = Column(
        SmallInteger,
        CheckConstraint("qubit_count >= 1 AND qubit_count <= 8", name="check_qubit_count_range"),
        nullable=False
    )
    gates = Column(JSONB, nullable=False)
    code_form = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="circuits")
    simulation_runs = relationship("SimulationRun", back_populates="circuit", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="circuit", cascade="all, delete-orphan")


class SimulationRun(Base):
    """
    simulation_runs table:
    Append-only execution ledger recording every simulated circuit iteration.
    INVARIANT: Never perform UPDATE operations against this table; only INSERT.
    """
    __tablename__ = "simulation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    circuit_id = Column(UUID(as_uuid=True), ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False, index=True)
    backend = Column(
        Text,
        CheckConstraint("backend IN ('aer', 'pennylane', 'cirq', 'real_ibm')", name="check_backend_type"),
        nullable=False,
        default="aer"
    )
    noise_level = Column(Float, nullable=False, default=0.0)
    counts = Column(JSONB, nullable=False)
    statevector = Column(JSONB, nullable=True)
    per_gate_states = Column(JSONB, nullable=True)
    duration_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    circuit = relationship("Circuit", back_populates="simulation_runs")
    predictions = relationship("Prediction", back_populates="actual_run")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    circuit_id = Column(UUID(as_uuid=True), ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False, index=True)
    predicted_distribution = Column(JSONB, nullable=False)
    actual_run_id = Column(UUID(as_uuid=True), ForeignKey("simulation_runs.id", ondelete="SET NULL"), nullable=True)
    locked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="predictions")
    circuit = relationship("Circuit", back_populates="predictions")
    actual_run = relationship("SimulationRun", back_populates="predictions")


class Concept(Base):
    """
    concepts table:
    Core domain concepts defining the pedagogical curriculum and knowledge graph.
    """
    __tablename__ = "concepts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)

    # Relationships
    masteries = relationship("ConceptMastery", back_populates="concept", cascade="all, delete-orphan")
    misconception_tags = relationship("MisconceptionTag", back_populates="concept", cascade="all, delete-orphan")


class ConceptMastery(Base):
    """
    concept_mastery table:
    Materialized fast-read source for student progress and adaptive recommendations.
    Composite PK on (user_id, concept_id).
    """
    __tablename__ = "concept_mastery"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True)
    mastery_score = Column(
        Float,
        CheckConstraint("mastery_score >= 0.0 AND mastery_score <= 1.0", name="check_mastery_score_range"),
        nullable=False,
        default=0.0
    )
    attempts = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="concept_masteries")
    concept = relationship("Concept", back_populates="masteries")


class MisconceptionTag(Base):
    """
    misconception_tags table:
    Fixed taxonomy of curated misconception classifications tied to concepts.
    """
    __tablename__ = "misconception_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, unique=True, nullable=False, index=True)
    display_label = Column(Text, nullable=False)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    concept = relationship("Concept", back_populates="misconception_tags")
    events = relationship("MisconceptionEvent", back_populates="tag", cascade="all, delete-orphan")


class MisconceptionEvent(Base):
    """
    misconception_events table:
    Logged student misconception occurrences detected rule-based or via AI classifier.
    """
    __tablename__ = "misconception_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    experiment_id = Column(UUID(as_uuid=True), nullable=True)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("misconception_tags.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(
        Text,
        CheckConstraint("source IN ('rule_based', 'ai_classified')", name="check_misconception_source"),
        nullable=False,
        default="ai_classified"
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="misconception_events")
    tag = relationship("MisconceptionTag", back_populates="events")


