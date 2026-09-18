"""add_google_oauth_fields

Revision ID: a8f2c3d1e9b4
Revises: 3a1f9c7b8d2e
Create Date: 2026-09-19 00:02:00.000000

Adds the following columns to the `users` table to support Google OAuth 2.0:
  - google_id:        VARCHAR(255) UNIQUE NULLABLE — Google's stable subject identifier.
                      Unique constraint + index prevents any duplicate Google accounts.
  - profile_picture:  TEXT NULLABLE — Google profile photo URL for display purposes.
  - auth_provider:    VARCHAR(20) NOT NULL DEFAULT 'email' — 'email' | 'google'.
                      Distinguishes login methods for correct error messaging.
  - updated_at:       TIMESTAMPTZ — tracks last user record modification.

Security note: password_hash is made nullable so Google-only users don't need a
local password. Email/password users always have a non-null password_hash —
the application layer enforces this invariant at signup.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f2c3d1e9b4'
down_revision: Union[str, Sequence[str], None] = '3a1f9c7b8d2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Google OAuth columns to users table."""
    # Make password_hash nullable: existing rows keep their hash,
    # new Google-only accounts will have NULL.
    op.alter_column('users', 'password_hash',
                    existing_type=sa.Text(),
                    nullable=True)

    # Google stable subject identifier — uniqueness enforced at DB level
    op.add_column('users', sa.Column(
        'google_id', sa.String(255), nullable=True
    ))
    op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)

    # Profile picture URL from Google — display only
    op.add_column('users', sa.Column(
        'profile_picture', sa.Text(), nullable=True
    ))

    # Auth provider discriminator — helps routing login errors correctly
    op.add_column('users', sa.Column(
        'auth_provider', sa.String(20), nullable=False,
        server_default='email'
    ))

    # Updated_at timestamp
    op.add_column('users', sa.Column(
        'updated_at', sa.DateTime(timezone=True),
        server_default=sa.text('now()'),
        nullable=False
    ))


def downgrade() -> None:
    """Remove Google OAuth columns from users table."""
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'auth_provider')
    op.drop_column('users', 'profile_picture')
    op.drop_index('ix_users_google_id', table_name='users')
    op.drop_column('users', 'google_id')
    # Restore password_hash NOT NULL — note: any Google-only rows will fail
    # if they have NULL password_hash. Only safe to downgrade on fresh DB.
    op.alter_column('users', 'password_hash',
                    existing_type=sa.Text(),
                    nullable=False)
