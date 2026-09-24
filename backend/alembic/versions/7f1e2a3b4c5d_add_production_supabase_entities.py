"""add_production_supabase_entities

Revision ID: 7f1e2a3b4c5d
Revises: 56bc0451d50b
Create Date: 2026-09-25 01:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7f1e2a3b4c5d'
down_revision: Union[str, Sequence[str], None] = '56bc0451d50b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. Profiles Table (Linked with Supabase Auth or internal accounts)
    if not insp.has_table('profiles'):
        op.create_table(
            'profiles',
            sa.Column('id', sa.Uuid().with_variant(sa.UUID(), 'postgresql'), primary_key=True),
            sa.Column('email', sa.String(length=255), unique=True, nullable=False),
            sa.Column('full_name', sa.String(length=255), nullable=True),
            sa.Column('role', sa.String(length=50), server_default='viewer', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        with op.batch_alter_table('profiles', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_profiles_email'), ['email'], unique=True)

    # 2. Data Uploads Table (Tracking CSV / JSON / AWS telemetry batches)
    if not insp.has_table('data_uploads'):
        op.create_table(
            'data_uploads',
            sa.Column('id', sa.Uuid().with_variant(sa.UUID(), 'postgresql'), primary_key=True),
            sa.Column('uploaded_by', sa.Uuid().with_variant(sa.UUID(), 'postgresql'), nullable=True),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('storage_path', sa.String(length=500), nullable=True),
            sa.Column('file_type', sa.String(length=50), server_default='csv', nullable=False),
            sa.Column('file_size', sa.BigInteger(), server_default='0', nullable=False),
            sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
            sa.Column('records_processed', sa.Integer(), server_default='0', nullable=False),
            sa.Column('records_failed', sa.Integer(), server_default='0', nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        with op.batch_alter_table('data_uploads', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_data_uploads_uploaded_by'), ['uploaded_by'], unique=False)
            batch_op.create_index(batch_op.f('ix_data_uploads_status'), ['status'], unique=False)

    # 3. Add last_seen to stations
    if insp.has_table('stations'):
        cols = [c['name'] for c in insp.get_columns('stations')]
        if 'last_seen' not in cols:
            with op.batch_alter_table('stations', schema=None) as batch_op:
                batch_op.add_column(sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True))

    # 4. Add raw value columns and optimized index to raw_readings (observations)
    if insp.has_table('raw_readings'):
        cols = [c['name'] for c in insp.get_columns('raw_readings')]
        with op.batch_alter_table('raw_readings', schema=None) as batch_op:
            if 'temperature_raw' not in cols:
                batch_op.add_column(sa.Column('temperature_raw', sa.Float(), nullable=True))
            if 'pressure_raw' not in cols:
                batch_op.add_column(sa.Column('pressure_raw', sa.Float(), nullable=True))
            if 'humidity_raw' not in cols:
                batch_op.add_column(sa.Column('humidity_raw', sa.Float(), nullable=True))

    # 5. Add title, acknowledged fields to alerts
    if insp.has_table('alerts'):
        cols = [c['name'] for c in insp.get_columns('alerts')]
        with op.batch_alter_table('alerts', schema=None) as batch_op:
            if 'title' not in cols:
                batch_op.add_column(sa.Column('title', sa.String(length=255), nullable=True))
            if 'acknowledged' not in cols:
                batch_op.add_column(sa.Column('acknowledged', sa.Boolean(), server_default='0', nullable=False))
            if 'acknowledged_by' not in cols:
                batch_op.add_column(sa.Column('acknowledged_by', sa.Uuid().with_variant(sa.UUID(), 'postgresql'), nullable=True))
            if 'acknowledged_at' not in cols:
                batch_op.add_column(sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True))

    # 6. Ensure system_tasks (maintenance_tasks) entity is properly present
    if not insp.has_table('system_tasks'):
        op.create_table(
            'system_tasks',
            sa.Column('id', sa.Uuid().with_variant(sa.UUID(), 'postgresql'), primary_key=True),
            sa.Column('station_id', sa.Uuid().with_variant(sa.UUID(), 'postgresql'), nullable=True),
            sa.Column('assigned_to', sa.Uuid().with_variant(sa.UUID(), 'postgresql'), nullable=True),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('failure_probability', sa.Float(), nullable=True),
            sa.Column('assigned_role', sa.String(length=50), nullable=False),
            sa.Column('priority', sa.String(length=50), server_default='medium', nullable=False),
            sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
            sa.Column('category', sa.String(length=50), server_default='general', nullable=False),
            sa.Column('station_code', sa.String(length=50), nullable=True),
            sa.Column('assigned_to_name', sa.String(length=255), nullable=True),
            sa.Column('due_date', sa.String(length=50), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
    else:
        cols = [c['name'] for c in insp.get_columns('system_tasks')]
        with op.batch_alter_table('system_tasks', schema=None) as batch_op:
            if 'station_id' not in cols:
                batch_op.add_column(sa.Column('station_id', sa.Uuid().with_variant(sa.UUID(), 'postgresql'), nullable=True))
            if 'assigned_to' not in cols:
                batch_op.add_column(sa.Column('assigned_to', sa.Uuid().with_variant(sa.UUID(), 'postgresql'), nullable=True))
            if 'failure_probability' not in cols:
                batch_op.add_column(sa.Column('failure_probability', sa.Float(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table('system_tasks'):
        cols = [c['name'] for c in insp.get_columns('system_tasks')]
        with op.batch_alter_table('system_tasks', schema=None) as batch_op:
            if 'failure_probability' in cols:
                batch_op.drop_column('failure_probability')
            if 'assigned_to' in cols:
                batch_op.drop_column('assigned_to')
            if 'station_id' in cols:
                batch_op.drop_column('station_id')

    if insp.has_table('alerts'):
        cols = [c['name'] for c in insp.get_columns('alerts')]
        with op.batch_alter_table('alerts', schema=None) as batch_op:
            if 'acknowledged_at' in cols:
                batch_op.drop_column('acknowledged_at')
            if 'acknowledged_by' in cols:
                batch_op.drop_column('acknowledged_by')
            if 'acknowledged' in cols:
                batch_op.drop_column('acknowledged')
            if 'title' in cols:
                batch_op.drop_column('title')

    if insp.has_table('raw_readings'):
        cols = [c['name'] for c in insp.get_columns('raw_readings')]
        with op.batch_alter_table('raw_readings', schema=None) as batch_op:
            if 'humidity_raw' in cols:
                batch_op.drop_column('humidity_raw')
            if 'pressure_raw' in cols:
                batch_op.drop_column('pressure_raw')
            if 'temperature_raw' in cols:
                batch_op.drop_column('temperature_raw')

    if insp.has_table('stations'):
        cols = [c['name'] for c in insp.get_columns('stations')]
        if 'last_seen' in cols:
            with op.batch_alter_table('stations', schema=None) as batch_op:
                batch_op.drop_column('last_seen')

    if insp.has_table('data_uploads'):
        op.drop_table('data_uploads')
    if insp.has_table('profiles'):
        op.drop_table('profiles')
