"""seed_superposition_misconception_tags

Revision ID: 20006ee23a47
Revises: 057653aef2fa
Create Date: 2026-09-12 12:38:53.807323

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20006ee23a47'
down_revision: Union[str, Sequence[str], None] = '057653aef2fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed fixed taxonomy of misconception tags tied to 'superposition'."""
    import uuid
    conn = op.get_bind()
    res = conn.execute(sa.text("SELECT id FROM concepts WHERE name = 'superposition'")).fetchone()
    if res:
        superposition_id = res[0]
        meta = sa.MetaData()
        meta.reflect(bind=conn, only=['misconception_tags'])
        misconception_tags_table = meta.tables['misconception_tags']
        op.bulk_insert(
            misconception_tags_table,
            [
                {
                    "id": uuid.uuid4(),
                    "name": "believes_qubit_is_secretly_definite_before_measurement",
                    "display_label": "Believes the qubit was secretly 0 or 1 all along",
                    "concept_id": superposition_id,
                },
                {
                    "id": uuid.uuid4(),
                    "name": "conflates_amplitude_with_probability",
                    "display_label": "Treats the amplitude value directly as the probability",
                    "concept_id": superposition_id,
                },
                {
                    "id": uuid.uuid4(),
                    "name": "expects_same_outcome_every_run",
                    "display_label": "Expects a deterministic, identical outcome on every run",
                    "concept_id": superposition_id,
                },
            ]
        )


def downgrade() -> None:
    """Remove superposition misconception tags."""
    op.execute(
        sa.text(
            "DELETE FROM misconception_tags WHERE name IN ("
            "'believes_qubit_is_secretly_definite_before_measurement', "
            "'conflates_amplitude_with_probability', "
            "'expects_same_outcome_every_run')"
        )
    )
