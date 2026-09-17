"""seed_gates_misconception_tags

Revision ID: 3a1f9c7b8d2e
Revises: 20006ee23a47
Create Date: 2026-09-17 02:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a1f9c7b8d2e'
down_revision: Union[str, Sequence[str], None] = '20006ee23a47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed fixed taxonomy of misconception tags tied to 'gates'."""
    import uuid
    conn = op.get_bind()
    res = conn.execute(sa.text("SELECT id FROM concepts WHERE name = 'gates'")).fetchone()
    if res:
        gates_id = res[0]
        meta = sa.MetaData()
        meta.reflect(bind=conn, only=['misconception_tags'])
        misconception_tags_table = meta.tables['misconception_tags']
        op.bulk_insert(
            misconception_tags_table,
            [
                {
                    "id": uuid.uuid4(),
                    "name": "believes_x_creates_superposition",
                    "display_label": "Confuses X (deterministic flip) with H (creates superposition)",
                    "concept_id": gates_id,
                },
                {
                    "id": uuid.uuid4(),
                    "name": "ignores_gate_order",
                    "display_label": "Doesn't account for gate application order affecting the result",
                    "concept_id": gates_id,
                },
                {
                    "id": uuid.uuid4(),
                    "name": "expects_z_to_change_measurement_probability",
                    "display_label": "Expects Z to change measurement outcomes on its own, not just phase",
                    "concept_id": gates_id,
                },
            ]
        )


def downgrade() -> None:
    """Remove gates misconception tags."""
    op.execute(
        sa.text(
            "DELETE FROM misconception_tags WHERE name IN ("
            "'believes_x_creates_superposition', "
            "'ignores_gate_order', "
            "'expects_z_to_change_measurement_probability')"
        )
    )
