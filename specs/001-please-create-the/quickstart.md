# Quickstart: MCP Character Service

**Date**: 2025-01-26  
**Purpose**: Validation scenarios for character service functionality

## Prerequisites
- MCP Character Service running on localhost:8011
- Database initialized with schema
- MCP client configured for testing

## Core User Scenarios

### Scenario 1: Create a Protagonist Character
**Objective**: Verify basic character creation with personality traits

**Steps**:
1. Use MCP tool `create_character` with the following data:
   ```json
   {
     "name": "Elena Rodriguez",
     "age": 28,
     "occupation": "Detective",
     "backstory": "Former military officer turned detective after witnessing corruption in her unit",
     "personality_traits": {
       "dominant_traits": [
         {"trait": "determined", "intensity": 9, "manifestation": "Never gives up on a case"},
         {"trait": "analytical", "intensity": 8, "manifestation": "Methodical problem-solving approach"},
         {"trait": "protective", "intensity": 7, "manifestation": "Strong desire to help victims"}
       ]
     },
     "narrative_role": "protagonist"
   }
   ```

**Expected Results**:
- Character created successfully with unique UUID
- All provided fields stored correctly
- Character retrievable by ID
- Response time < 200ms

**Validation**:
- Call `get_character` with returned ID
- Verify all fields match input data
- Confirm personality traits structure is preserved

### Scenario 2: Create Character Relationships
**Objective**: Test bidirectional relationship creation and consistency

**Steps**:
1. Create second character (Marcus Chen - mentor figure):
   ```json
   {
     "name": "Marcus Chen",
     "age": 45,
     "occupation": "Police Captain",
     "narrative_role": "mentor"
   }
   ```

2. Create relationship between Elena and Marcus:
   ```json
   {
     "character_a_id": "[Elena's UUID]",
     "character_b_id": "[Marcus's UUID]",
     "relationship_type": "mentor",
     "strength": 8,
     "history": "Marcus recruited Elena and became her mentor on the force",
     "is_mutual": true
   }
   ```

**Expected Results**:
- Relationship created with unique ID
- Bidirectional consistency maintained
- Both characters show the relationship when queried

**Validation**:
- Call `get_character_relationships` for both characters
- Verify relationship appears for both with correct metadata
- Confirm relationship strength and type are preserved

### Scenario 3: Character Search and Discovery
**Objective**: Test character search functionality across different criteria

**Steps**:
1. Search by name: `search_characters` with query "Elena"
2. Search by role: `search_characters` with narrative_role "protagonist"
3. Search by trait: `search_characters` with personality_traits ["determined"]

**Expected Results**:
- Name search returns Elena Rodriguez
- Role search returns all protagonists
- Trait search returns characters with "determined" trait
- All searches complete within 100ms (sub-200ms requirement)

**Validation**:
- Verify search results contain expected characters
- Confirm result metadata includes relevant fields
- Test pagination with limit/offset parameters

### Scenario 4: Character Profile Updates
**Objective**: Verify character updates preserve relationships and consistency

**Steps**:
1. Update Elena's emotional state:
   ```json
   {
     "character_id": "[Elena's UUID]",
     "updates": {
       "emotional_state": {
         "current_mood": "focused",
         "stress_level": 6,
         "dominant_emotion": "determination"
       },
       "backstory": "Former military officer turned detective after witnessing corruption in her unit. Recently promoted to lead detective."
     }
   }
   ```

**Expected Results**:
- Character updated successfully
- Relationships remain intact
- Version field incremented for optimistic locking
- Update timestamp reflects change

**Validation**:
- Retrieve updated character and verify changes
- Confirm relationships still exist and are unchanged
- Check that other characters' relationships to Elena are preserved

### Scenario 5: Complex Relationship Network
**Objective**: Test relationship traversal and network consistency

**Steps**:
1. Create third character (Sarah Kim - colleague):
   ```json
   {
     "name": "Sarah Kim",
     "age": 32,
     "occupation": "Forensic Analyst",
     "narrative_role": "ally"
   }
   ```

2. Create professional relationship Elena ↔ Sarah
3. Create friendship relationship Marcus ↔ Sarah
4. Query relationship network for each character

**Expected Results**:
- All relationships created successfully
- No circular dependency issues
- Relationship queries return complete network information
- Performance remains under 200ms for complex queries

**Validation**:
- Verify each character shows correct relationship count
- Test relationship type filtering
- Confirm bidirectional consistency across all relationships

## Performance Validation

### Latency Testing
**Objective**: Verify constitutional performance requirements

**Test Cases**:
1. Character creation: Must complete < 200ms
2. Character retrieval: Must complete < 100ms
3. Character search (1000+ characters): Must complete < 100ms
4. Relationship creation: Must complete < 200ms
5. Complex relationship queries: Must complete < 200ms

**Load Testing**:
- 10 concurrent character creations
- 50 concurrent character searches
- 100 concurrent character retrievals

### Memory Usage Validation
**Objective**: Verify memory constraints

**Test Cases**:
- Service startup memory baseline
- Memory usage with 1000 characters loaded
- Memory usage during concurrent operations
- Memory leak detection over extended operation

## Error Handling Validation

### Invalid Input Testing
1. Create character with missing required fields
2. Create relationship with non-existent character IDs
3. Update character with invalid data types
4. Search with malformed query parameters

**Expected Results**:
- Appropriate error messages returned
- Service remains stable
- No data corruption occurs
- Error responses follow MCP protocol standards

### Concurrent Access Testing
1. Multiple agents creating characters simultaneously
2. Simultaneous updates to same character
3. Concurrent relationship modifications

**Expected Results**:
- Optimistic locking prevents data corruption
- Appropriate conflict resolution
- No deadlocks or race conditions

## Health Check Validation

### Service Health
1. Call health check endpoint
2. Verify database connectivity
3. Confirm MCP protocol readiness
4. Check memory and performance metrics

**Expected Results**:
- Health check returns 200 OK
- All dependencies report healthy
- Performance metrics within acceptable ranges

## Success Criteria

✅ **All scenarios complete successfully**  
✅ **Performance requirements met (200ms p95 latency)**  
✅ **Memory usage under 512MB**  
✅ **No data corruption or consistency issues**  
✅ **MCP protocol compliance verified**  
✅ **Error handling robust and informative**  
✅ **Concurrent access handled correctly**  
✅ **Health checks pass consistently**

## Troubleshooting

### Common Issues
- **Slow queries**: Check database indexes and connection pool
- **Memory leaks**: Monitor object lifecycle and caching
- **Relationship inconsistencies**: Verify bidirectional update triggers
- **MCP protocol errors**: Validate tool schemas and responses

### Debug Commands
- Check service logs for structured JSON output
- Monitor Prometheus metrics for performance data
- Verify database constraints and foreign keys
- Test MCP tool contracts independently

This quickstart validates all core functionality and constitutional requirements for the MCP Character Service.
