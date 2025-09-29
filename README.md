# MCP Character Service

An MCP (Model Context Protocol) service for character management in the movie generation platform. Provides comprehensive character creation, management, and profile generation capabilities.

## Features

### Core Character Management
- Create, read, update, and delete characters
- Character relationship management
- Search and filtering capabilities
- Character archetype system

### Character Profile Generation (NEW)
- Generate character profiles from scene lists and concept briefs
- Automatic character extraction from episodes
- Deduplication with alphabetical suffix system
- LLM-powered motivation and visual signature generation
- PayloadCMS registry integration
- Error handling for insufficient guidance scenarios

## Architecture

### Components

1. **MCP Tools**: Character operation endpoints
   - `create_character` - Create new characters
   - `get_character` - Retrieve character details
   - `search_characters` - Search and filter characters
   - `create_relationship` - Create character relationships
   - `get_character_relationships` - Retrieve relationships
   - `update_character` - Update character data
   - `generate_character_profiles` - Generate profiles from scenes (NEW)

2. **Services**:
   - `CharacterService` - Core character operations
   - `PayloadService` - PayloadCMS integration (NEW)
   - `PromptService` - LLM interaction service (NEW)
   - `RelationshipService` - Relationship management
   - `SearchService` - Character search and filtering

3. **Models**:
   - `Character` - Main character entity
   - `Archetype` - Character archetype definitions
   - `Personality` - Character personality traits
   - `Relationship` - Character relationships

### New Character Profile Generation Flow

1. **Input Processing**: Validates scene lists and concept briefs
2. **Registry Sync**: Queries PayloadCMS for existing characters
3. **Character Extraction**: Extracts characters from scenes with context
4. **Deduplication**: Handles name conflicts with alphabetical suffixes
5. **Profile Generation**: Uses LLM to generate motivations and visual signatures
6. **Registry Update**: Asynchronously updates character registry
7. **Response Assembly**: Returns structured character profiles

## Configuration

### Environment Variables

```bash
# PayloadCMS Integration
PAYLOAD_CMS_URL=http://localhost:3001
PAYLOAD_CMS_API_KEY=your-payload-cms-api-key
PAYLOAD_CMS_TIMEOUT=30

# LLM Provider Configuration
LLM_PROVIDER_URL=https://api.openai.com/v1/chat/completions
LLM_API_KEY=your-llm-api-key
LLM_MODEL_NAME=gpt-3.5-turbo
LLM_TIMEOUT=60
LLM_MAX_TOKENS=200
LLM_TEMPERATURE=0.7

# Character Generation Settings
MAX_CHARACTERS_PER_REQUEST=4
PROFILE_GENERATION_TIMEOUT=300
MOTIVATION_WORD_LIMIT=50
VISUAL_SIGNATURE_WORD_LIMIT=40

# Feature Flags
ENABLE_PAYLOAD_INTEGRATION=true
ENABLE_LLM_INTEGRATION=true
```

### Database Setup

The service uses PostgreSQL with SQLAlchemy for data persistence:

```sql
-- Characters table structure
CREATE TABLE characters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    nickname VARCHAR(50),
    age INTEGER,
    gender VARCHAR(50),
    occupation VARCHAR(100),
    backstory TEXT,
    physical_description TEXT,
    personality_traits JSONB,
    emotional_state JSONB,
    narrative_role VARCHAR(20),
    archetype_id UUID REFERENCES archetypes(id),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## API Usage

### Generate Character Profiles

```json
{
  "tool": "generate_character_profiles",
  "arguments": {
    "scene_list": [
      {
        "scene_number": 1,
        "primary_characters": ["Rhea", "Marcus"],
        "secondary_characters": ["Guard"],
        "goal": "Escape from prison"
      },
      {
        "scene_number": 2,
        "primary_characters": ["Rhea"],
        "goal": "Find the hidden treasure"
      }
    ],
    "concept_brief": {
      "genre_tags": ["action", "adventure"],
      "tone_keywords": ["dramatic", "suspenseful"],
      "core_conflict": "Fight against corruption"
    },
    "project_id": "project-123"
  }
}
```

**Response:**
```json
{
  "success": true,
  "character_profiles": [
    {
      "name": "Rhea",
      "role": "protagonist",
      "motivation": "Seeks justice and freedom from oppressive system that wrongfully imprisoned her",
      "visual_signature": "Athletic build, determined expression, practical clothing suitable for action",
      "relationships": [],
      "continuity_notes": [
        "Appears in scenes: 1, 2",
        "Multiple goals across 2 scenes"
      ]
    },
    {
      "name": "Marcus",
      "role": "support",
      "motivation": "Loyal companion willing to risk everything to help his friend escape",
      "visual_signature": "Stocky frame, weathered face, carries himself with quiet confidence",
      "relationships": [],
      "continuity_notes": [
        "Primary goal: Escape from prison..."
      ]
    }
  ],
  "unresolved_references": []
}
```

### Error Handling

The service handles several error scenarios:

1. **Lacking Guidance**: When insufficient information is provided
   ```json
   {
     "success": false,
     "error": "lacking_guidance",
     "message": "Insufficient guidance for character: Unknown Character",
     "character_profiles": [],
     "unresolved_references": ["Unknown Character"]
   }
   ```

2. **Validation Errors**: For malformed input data
3. **Service Errors**: PayloadCMS or LLM provider failures

## Character Deduplication

The service implements intelligent character deduplication:

1. **Registry Matching**: Case-insensitive matching against existing characters
2. **Alphabetical Suffixes**: Duplicate names get suffixes (A, B, C, etc.)
3. **Canonical Names**: Uses registry names for consistency

Example:
- First "John" → "John"
- Second "John" → "John A"  
- Third "John" → "John B"

## Prompt Templates

Character generation uses customizable prompt templates located in `src/prompts/`:

- `master_reference.prompt` - Main template for character generation
- Additional genre-specific templates can be added

Template variables:
- `{genre_tags}` - Project genre tags
- `{tone_keywords}` - Tone descriptors
- `{core_conflict}` - Main story conflict
- `{name}` - Character name
- `{role}` - Character role
- `{scene_numbers}` - Scenes character appears in
- `{goals}` - Character goals from scenes

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# All tests
pytest
```

### Running the Service

```bash
# Development
python -m src.main

# Production
docker-compose up character-service
```

### Adding New Tools

1. Create tool class in `src/mcp/tools/`
2. Implement required methods: `get_schema()`, `validate_input()`, `execute()`
3. Register in `src/mcp/server.py`
4. Add tests in `tests/unit/`

## Monitoring and Observability

The service includes comprehensive monitoring:

- **Metrics**: Prometheus metrics for operations, latency, errors
- **Logging**: Structured logging with request tracing
- **Health Checks**: PayloadCMS and database health monitoring

Key metrics:
- `character_creator.profile_count` - Number of profiles generated
- `character_creator.unresolved_reference_rate` - Rate of unresolved characters
- `character_creator.latency_ms` - Profile generation latency
- `character_creator.error_count` - Error count

## Integration

### PayloadCMS Schema

The service expects a `characters` collection in PayloadCMS with:

**Required Fields:**
- `name` (string) - Character name
- `project_id` (string) - Project identifier

**Optional Fields:**
- `role` (string) - Character role
- `motivation` (text) - Character motivation
- `visual_signature` (text) - Visual description
- `relationships` (array) - Character relationships
- `continuity_notes` (array) - Continuity notes

### Downstream Services

Character profiles are consumed by:
- **Storyboard Artist**: Uses visual signatures for scene rendering
- **Image Generation**: Creates character visualizations
- **Story Bible Service**: Maintains character continuity

## Troubleshooting

### Common Issues

1. **PayloadCMS Connection Failed**
   - Check `PAYLOAD_CMS_URL` and `PAYLOAD_CMS_API_KEY`
   - Verify PayloadCMS service is running
   - Check network connectivity

2. **LLM Provider Errors**
   - Verify `LLM_PROVIDER_URL` and `LLM_API_KEY`
   - Check API rate limits
   - Review prompt templates for formatting issues

3. **Character Deduplication Issues**
   - Verify PayloadCMS character collection structure
   - Check project_id filtering
   - Review registry query parameters

4. **Database Connection Issues**
   - Check `DATABASE_URL` configuration
   - Verify PostgreSQL service status
   - Run database migrations

### Debugging

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
export DEBUG=true
```

Check service health:
```bash
curl http://localhost:8011/health
```

## Contributing

1. Follow existing code patterns and conventions
2. Add comprehensive tests for new features
3. Update documentation for API changes
4. Ensure all services integrate properly
5. Add monitoring for new operations

## License

[Your License Here]