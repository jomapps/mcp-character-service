"""Initial schema for MCP Character Service

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-01-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    
    # Create archetypes table
    op.create_table('archetypes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('default_traits', sa.JSON(), nullable=True),
        sa.Column('narrative_function', sa.String(length=100), nullable=True),
        sa.Column('common_motivations', sa.JSON(), nullable=True),
        sa.Column('relationship_patterns', sa.JSON(), nullable=True),
        sa.Column('growth_patterns', sa.JSON(), nullable=True),
        sa.Column('examples', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create characters table
    op.create_table('characters',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('nickname', sa.String(length=50), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('gender', sa.String(length=50), nullable=True),
        sa.Column('occupation', sa.String(length=100), nullable=True),
        sa.Column('backstory', sa.Text(), nullable=True),
        sa.Column('physical_description', sa.Text(), nullable=True),
        sa.Column('personality_traits', sa.JSON(), nullable=True),
        sa.Column('emotional_state', sa.JSON(), nullable=True),
        sa.Column('narrative_role', sa.Enum('protagonist', 'antagonist', 'mentor', 'ally', 'neutral', 'comic_relief', name='narrative_role_enum'), nullable=True),
        sa.Column('archetype_id', sa.UUID(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['archetype_id'], ['archetypes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create personalities table
    op.create_table('personalities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('character_id', sa.UUID(), nullable=False),
        sa.Column('dominant_traits', sa.JSON(), nullable=True),
        sa.Column('secondary_traits', sa.JSON(), nullable=True),
        sa.Column('motivations', sa.JSON(), nullable=True),
        sa.Column('fears', sa.JSON(), nullable=True),
        sa.Column('values', sa.JSON(), nullable=True),
        sa.Column('behavioral_patterns', sa.JSON(), nullable=True),
        sa.Column('growth_arc', sa.JSON(), nullable=True),
        sa.Column('psychological_profile', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('character_id')
    )
    
    # Create relationships table
    op.create_table('relationships',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('character_a_id', sa.UUID(), nullable=False),
        sa.Column('character_b_id', sa.UUID(), nullable=False),
        sa.Column('relationship_type', sa.Enum('family', 'romantic', 'friendship', 'professional', 'adversarial', 'mentor', name='relationship_type_enum'), nullable=False),
        sa.Column('strength', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', 'complicated', 'developing', name='relationship_status_enum'), nullable=False, default='active'),
        sa.Column('history', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('is_mutual', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('character_a_id != character_b_id', name='no_self_relationship'),
        sa.CheckConstraint('strength >= 1 AND strength <= 10', name='valid_strength_range'),
        sa.ForeignKeyConstraint(['character_a_id'], ['characters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['character_b_id'], ['characters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('character_a_id', 'character_b_id', 'relationship_type')
    )
    
    # Create indexes for performance
    op.create_index('idx_characters_name', 'characters', ['name'])
    op.create_index('idx_characters_nickname', 'characters', ['nickname'])
    op.create_index('idx_characters_narrative_role', 'characters', ['narrative_role'])
    op.create_index('idx_characters_archetype_id', 'characters', ['archetype_id'])
    op.create_index('idx_characters_created_at', 'characters', ['created_at'])
    
    op.create_index('idx_relationships_character_a', 'relationships', ['character_a_id'])
    op.create_index('idx_relationships_character_b', 'relationships', ['character_b_id'])
    op.create_index('idx_relationships_type', 'relationships', ['relationship_type'])
    op.create_index('idx_relationships_status', 'relationships', ['status'])
    
    op.create_index('idx_personalities_character_id', 'personalities', ['character_id'])
    
    op.create_index('idx_archetypes_name', 'archetypes', ['name'])
    op.create_index('idx_archetypes_is_active', 'archetypes', ['is_active'])
    
    # Create JSON indexes for personality traits (PostgreSQL specific)
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("CREATE INDEX idx_characters_personality_traits ON characters USING GIN (personality_traits)")
        op.execute("CREATE INDEX idx_personalities_dominant_traits ON personalities USING GIN (dominant_traits)")


def downgrade() -> None:
    """Downgrade database schema."""
    
    # Drop indexes
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("DROP INDEX IF EXISTS idx_characters_personality_traits")
        op.execute("DROP INDEX IF EXISTS idx_personalities_dominant_traits")
    
    op.drop_index('idx_archetypes_is_active', table_name='archetypes')
    op.drop_index('idx_archetypes_name', table_name='archetypes')
    op.drop_index('idx_personalities_character_id', table_name='personalities')
    op.drop_index('idx_relationships_status', table_name='relationships')
    op.drop_index('idx_relationships_type', table_name='relationships')
    op.drop_index('idx_relationships_character_b', table_name='relationships')
    op.drop_index('idx_relationships_character_a', table_name='relationships')
    op.drop_index('idx_characters_created_at', table_name='characters')
    op.drop_index('idx_characters_archetype_id', table_name='characters')
    op.drop_index('idx_characters_narrative_role', table_name='characters')
    op.drop_index('idx_characters_nickname', table_name='characters')
    op.drop_index('idx_characters_name', table_name='characters')
    
    # Drop tables
    op.drop_table('relationships')
    op.drop_table('personalities')
    op.drop_table('characters')
    op.drop_table('archetypes')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS relationship_status_enum")
    op.execute("DROP TYPE IF EXISTS relationship_type_enum")
    op.execute("DROP TYPE IF EXISTS narrative_role_enum")
