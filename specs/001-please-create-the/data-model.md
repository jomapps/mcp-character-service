# Data Model: MCP Character Service

**Date**: 2025-01-26  
**Phase**: 1 - Entity Design and Relationships

## Core Entities

### Character
**Purpose**: Core entity representing a story character with complete personality profile

**Fields**:
- `id` (UUID): Unique identifier, primary key
- `name` (String, required): Character's full name, indexed for search
- `nickname` (String, optional): Common name or alias
- `age` (Integer, optional): Character's age
- `gender` (String, optional): Character's gender identity
- `occupation` (String, optional): Character's profession or role
- `backstory` (Text, optional): Character's history and background
- `physical_description` (Text, optional): Appearance and physical traits
- `personality_traits` (JSON): Structured personality attributes
- `emotional_state` (JSON): Current emotional status and mood
- `narrative_role` (String): Story function (protagonist, antagonist, mentor, etc.)
- `archetype_id` (UUID, optional): Reference to character archetype template
- `created_at` (Timestamp): Creation timestamp
- `updated_at` (Timestamp): Last modification timestamp
- `version` (Integer): Optimistic locking version field

**Validation Rules**:
- Name must be non-empty and unique within story context
- Personality traits must follow predefined schema structure
- Emotional state must include valid emotion categories
- Narrative role must be from predefined enum values

**Indexes**:
- Primary: `id`
- Search: `name`, `nickname`
- Filtering: `narrative_role`, `archetype_id`
- JSON: `personality_traits.dominant_traits`

### Relationship
**Purpose**: Bidirectional connections between characters with metadata

**Fields**:
- `id` (UUID): Unique identifier, primary key
- `character_a_id` (UUID, required): First character reference, foreign key
- `character_b_id` (UUID, required): Second character reference, foreign key
- `relationship_type` (String, required): Type of relationship
- `strength` (Integer): Relationship intensity (1-10 scale)
- `status` (String): Current relationship status
- `history` (Text, optional): Relationship development history
- `metadata` (JSON): Additional relationship attributes
- `is_mutual` (Boolean): Whether relationship is bidirectional
- `created_at` (Timestamp): Relationship establishment date
- `updated_at` (Timestamp): Last modification timestamp

**Validation Rules**:
- Character A and B must be different characters
- Relationship type must be from predefined enum
- Strength must be between 1-10
- Bidirectional consistency must be maintained

**Relationship Types**:
- `family`: Family relationships (parent, sibling, etc.)
- `romantic`: Romantic connections (lover, spouse, ex-partner)
- `friendship`: Platonic relationships (friend, best friend, acquaintance)
- `professional`: Work-related connections (colleague, boss, employee)
- `adversarial`: Conflict relationships (enemy, rival, nemesis)
- `mentor`: Guidance relationships (mentor, student, teacher)

**Indexes**:
- Primary: `id`
- Lookup: `character_a_id`, `character_b_id`
- Filtering: `relationship_type`, `status`
- Composite: `(character_a_id, character_b_id)` unique constraint

### Personality
**Purpose**: Detailed psychological profile with trait evolution tracking

**Fields**:
- `id` (UUID): Unique identifier, primary key
- `character_id` (UUID, required): Character reference, foreign key
- `dominant_traits` (JSON): Primary personality characteristics
- `secondary_traits` (JSON): Supporting personality features
- `motivations` (JSON): Character drives and goals
- `fears` (JSON): Character anxieties and phobias
- `values` (JSON): Core beliefs and principles
- `behavioral_patterns` (JSON): Typical behavior descriptions
- `growth_arc` (JSON): Character development trajectory
- `psychological_profile` (Text): Detailed personality analysis
- `created_at` (Timestamp): Profile creation date
- `updated_at` (Timestamp): Last modification timestamp

**Validation Rules**:
- Must have at least one dominant trait
- Traits must follow standardized personality taxonomy
- Motivations and fears must be non-contradictory
- Growth arc must have logical progression

**Personality Trait Schema**:
```json
{
  "dominant_traits": [
    {
      "trait": "string",
      "intensity": "integer (1-10)",
      "manifestation": "string"
    }
  ],
  "motivations": [
    {
      "type": "string",
      "description": "string",
      "priority": "integer (1-10)"
    }
  ]
}
```

### Archetype
**Purpose**: Template for common character roles with predefined patterns

**Fields**:
- `id` (UUID): Unique identifier, primary key
- `name` (String, required): Archetype name (Hero, Villain, Mentor, etc.)
- `description` (Text): Archetype description and purpose
- `default_traits` (JSON): Standard personality traits for this archetype
- `narrative_function` (String): Story role and purpose
- `common_motivations` (JSON): Typical drives for this archetype
- `relationship_patterns` (JSON): Common relationship types
- `growth_patterns` (JSON): Typical character development arcs
- `examples` (JSON): Famous characters of this archetype
- `is_active` (Boolean): Whether archetype is available for use
- `created_at` (Timestamp): Creation timestamp
- `updated_at` (Timestamp): Last modification timestamp

**Validation Rules**:
- Name must be unique
- Default traits must follow personality schema
- Narrative function must be defined
- Must have at least one common motivation

## Entity Relationships

### Character ↔ Relationship
- **One-to-Many**: One character can have multiple relationships
- **Bidirectional**: Relationships reference both characters
- **Cascade**: Character deletion removes associated relationships
- **Integrity**: Foreign key constraints ensure valid character references

### Character ↔ Personality
- **One-to-One**: Each character has one detailed personality profile
- **Cascade**: Character deletion removes personality profile
- **Dependency**: Personality cannot exist without character

### Character ↔ Archetype
- **Many-to-One**: Multiple characters can use same archetype
- **Optional**: Characters can exist without archetype assignment
- **Template**: Archetype provides default values for character creation

### Relationship Bidirectionality
- **Consistency**: If A relates to B, B must relate to A (when mutual)
- **Validation**: Database triggers ensure bidirectional consistency
- **Metadata**: Each direction can have different metadata

## Data Integrity Rules

### Character Constraints
1. Name uniqueness within story context
2. Valid personality trait structure
3. Consistent emotional state values
4. Non-null required fields

### Relationship Constraints
1. No self-referential relationships
2. Unique character pair combinations
3. Valid relationship type values
4. Bidirectional consistency maintenance

### Personality Constraints
1. At least one dominant trait required
2. Trait intensity values within valid range
3. Non-contradictory motivations and fears
4. Logical growth arc progression

## Performance Considerations

### Indexing Strategy
- Primary keys for fast lookups
- Name fields for character search
- JSON path indexes for trait queries
- Composite indexes for relationship queries

### Query Optimization
- Character search by traits using JSON operators
- Relationship traversal using recursive CTEs
- Bulk operations for character ensemble management
- Prepared statements for common queries

### Caching Strategy
- Frequently accessed characters in Redis
- Archetype templates cached at application level
- Relationship graphs cached for complex queries
- Cache invalidation on character updates

This data model supports all functional requirements while maintaining referential integrity, performance targets, and constitutional compliance.
