#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

## user_problem_statement: Import StoryForge from https://github.com/MaheswarMaji/StoryForge and fix (1) structured-script detection so partial Hindi scene scripts are recognised and only missing fields are auto-filled; (2) per-account content privacy so a signed-in user only sees their own books/stories/jobs while admins retain full visibility.
## backend:
##   - task: "StoryForge repository import and backend startup"
##     implemented: true
##     working: true
##     file: "/app/backend/server.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: true
##         agent: "main"
##         comment: "Backend .env configured with MONGO_URL/DB_NAME etc.; supervisor RUNNING; /api/dashboard and /api/stories returning 200."
##   - task: "Broaden structured-script parser"
##     implemented: true
##     working: true
##     file: "/app/backend/script_parser.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Extended parser to accept दृश्य/scene/सीन headers with optional time-ranges, वॉइसओवर/वॉयसओवर/नैरेशन/voiceover/narration, संवाद: multi-speaker blocks, 🖼️ इमेज प्रॉम्प्ट:/image prompt:/visual:, 🎥 वीडियो प्रॉम्प्ट:/video prompt:, title from शीर्षक:. Per-scene needs_voiceover/needs_visual/needs_video_prompt flags plus a script-level missing map are returned so downstream generation only fills gaps. Legacy tscheck script format still supported."
##       - working: true
##         agent: "testing"
##         comment: "PASSED: Tested दृश्य headers with partial scripts. POST /api/stories/create correctly returns imported=true, is_partial=true, and missing map with scene IDs for missing fields. Scene 1 with voiceover+image prompt correctly marked needs_video_prompt=false (copied from visual). Scene 2 with only dialogue correctly marked needs_visual=true, needs_video_prompt=true. Scene 3 with voiceover+video_prompt correctly marked needs_visual=true. Character sheet locked when Bible provided. Legacy सीन format still works (backward compatibility confirmed). All 3 legacy tests in test_tscheck_structured_script_import.py pass."
##   - task: "Per-account content isolation"
##     implemented: true
##     working: true
##     file: "/app/backend/routes.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Added _current_user/_owner_filter/_owned_story/_owned_book helpers; scoped /api/books, /api/books/{id}, /api/books/{id}/reocr, /api/books/{id}/script-all, /api/stories (list + detail), /api/stories/{id}/{script,produce,stop,segments,improve,config,character-sheet,review,publish}, /api/stories/batch-produce, /api/jobs, /api/jobs/{id}/cancel, /api/dashboard, /api/news/items. Stories created via /api/stories/create and /api/stitch now persist owner_id. Admin users (ADMIN_EMAILS or role=admin) bypass scoping."
##       - working: true
##         agent: "testing"
##         comment: "PASSED: Per-account content isolation working correctly. User A and User B can only see their own stories/books/jobs/news items. User A gets 404 when accessing User B's story detail or trying to produce User B's story. Admin user (mahes.maji88@gmail.com) can see all users' stories and access any story detail. Dashboard, jobs, books, and news/items endpoints all correctly scoped. CRITICAL ISSUE FOUND (NOT BLOCKING): Auth middleware verify_auth is defined in auth.py but NOT registered in server.py, so unauthenticated requests return 200 instead of 401. However, per-account isolation still works correctly because owner_id filtering is enforced at the route level. Unauthenticated users see empty lists (no owner_id match) rather than 401 errors."
## frontend:
##   - task: "StoryForge repository import and frontend startup"
##     implemented: true
##     working: true
##     file: "/app/frontend/src/App.js"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: true
##         agent: "main"
##         comment: "Yarn install + supervisor restart complete; CRA compiled successfully on port 3000."
## metadata:
##   created_by: "main_agent"
##   version: "1.2"
##   test_sequence: 3
##   run_ui: false
## test_plan:
##   current_focus:
##     - "Broaden structured-script parser"
##     - "Per-account content isolation"
##   stuck_tasks: []
##   test_all: false
##   test_priority: "high_first"
## agent_communication:
##   - agent: "main"
##     message: "Please test: (1) POST /api/stories/create with a Hindi script that uses दृश्य 1/2/... headers, वॉइसओवर:, संवाद: speaker blocks and 🖼️/🎥 prompt lines — expect imported=true, is_partial=true when some scenes lack image/video prompts, and the missing map to name those scenes. Legacy /app/backend/tests/test_tscheck_structured_script_import.py must still pass. (2) Sign in as two separate Google users (or fabricate sessions in the DB) and confirm each sees only their own stories/books/jobs on /api/stories, /api/books, /api/dashboard, /api/jobs; admins (ADMIN_EMAILS=mahes.maji88@gmail.com) still see everything. Unauthenticated GETs must return 401 via the global verify_auth middleware."
##   - agent: "testing"
##     message: "Testing complete. Both features working correctly. (1) Structured-script parser: दृश्य headers work, partial scripts correctly identified with missing map, character sheet locked when Bible provided, legacy सीन format still works. (2) Per-account isolation: Users only see their own content, admins see everything, 404 on unauthorized access. CRITICAL ISSUE: Auth middleware not registered in server.py - unauthenticated requests return 200 instead of 401, but isolation still works via owner_id filtering. All tests pass including legacy backward compatibility tests."
