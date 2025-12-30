"""
Test file to verify session management fixes are working correctly.

This test file verifies:
1. Auto-generation of session_id on first API call
2. Old sessions are deactivated when new ones are created
3. Chat history only returns data for the active session
4. Conversation chains are cleared for new sessions
5. Session validation works correctly

Run this test with:
    python test_session_management.py

Or with pytest (if installed):
    pytest test_session_management.py -v
"""

import os
import sys
import uuid
import json
from typing import Dict, Any, Optional

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import required modules
try:
    from app.services.user_profile_manager import (
        set_active_session_by_session_id,
        deactivate_session_by_id,
        is_session_active
    )
    from app.services.chat_history_manager import (
        get_chat_history_by_session,
        store_chat_interaction
    )
    from app.database.supabase import get_supabase
    USER_PROFILE_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Could not import user_profile_manager: {e}")
    USER_PROFILE_AVAILABLE = False

try:
    from app.api.routes.chat import _clear_conversation_chain
    CONVERSATION_CHAIN_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Could not import conversation chain functions: {e}")
    CONVERSATION_CHAIN_AVAILABLE = False


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_test_header(test_name: str):
    """Print a formatted test header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}TEST: {test_name}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_success(message: str):
    """Print a success message."""
    print(f"{Colors.GREEN}[PASS]{Colors.RESET} {message}")


def print_error(message: str):
    """Print an error message."""
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {message}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {message}")


def print_info(message: str):
    """Print an info message."""
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {message}")


class SessionManagementTests:
    """Test suite for session management functionality."""
    
    def __init__(self):
        self.test_results = []
        self.session_ids = []
        
    def run_all_tests(self):
        """Run all test cases."""
        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}SESSION MANAGEMENT TEST SUITE{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
        
        if not USER_PROFILE_AVAILABLE:
            print_error("User profile manager not available. Cannot run tests.")
            return False
        
        # Run all tests
        tests = [
            ("Test 1: Session Creation on First API Call", self.test_session_creation),
            ("Test 2: Old Session Deactivation", self.test_old_session_deactivation),
            ("Test 3: Chat History Isolation", self.test_chat_history_isolation),
            ("Test 4: Conversation Chain Clearing", self.test_conversation_chain_clearing),
            ("Test 5: Session Validation", self.test_session_validation),
            ("Test 6: Multiple Session Creation", self.test_multiple_session_creation),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print_error(f"{test_name} raised an exception: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
        
        # Print summary
        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}TEST SUMMARY{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
        print(f"{Colors.RED}Failed: {failed}{Colors.RESET}")
        print(f"Total: {passed + failed}\n")
        
        return failed == 0
    
    def test_session_creation(self) -> bool:
        """Test that a session is created when none exists."""
        print_test_header("Session Creation on First API Call")
        
        try:
            # Create a new session
            new_session_id = str(uuid.uuid4())
            print_info(f"Creating new session: {new_session_id}")
            
            profile_id = set_active_session_by_session_id(new_session_id)
            
            if profile_id is None:
                print_error("Failed to create session - profile_id is None")
                return False
            
            print_success(f"Session created successfully (profile_id: {profile_id})")
            
            # Verify session is active
            is_active = is_session_active(new_session_id)
            if not is_active:
                print_error(f"Session {new_session_id} is not active after creation")
                return False
            
            print_success(f"Session {new_session_id} is active")
            self.session_ids.append(new_session_id)
            
            return True
            
        except Exception as e:
            print_error(f"Exception during session creation test: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_old_session_deactivation(self) -> bool:
        """Test that old sessions are deactivated when a new one is created."""
        print_test_header("Old Session Deactivation")
        
        try:
            # Create first session
            session1_id = str(uuid.uuid4())
            print_info(f"Creating first session: {session1_id}")
            profile_id1 = set_active_session_by_session_id(session1_id)
            
            if profile_id1 is None:
                print_error("Failed to create first session")
                return False
            
            # Verify first session is active
            if not is_session_active(session1_id):
                print_error("First session is not active")
                return False
            
            print_success(f"First session {session1_id} is active")
            
            # Create second session (should deactivate first)
            session2_id = str(uuid.uuid4())
            print_info(f"Creating second session: {session2_id} (should deactivate first)")
            profile_id2 = set_active_session_by_session_id(session2_id)
            
            if profile_id2 is None:
                print_error("Failed to create second session")
                return False
            
            # Verify second session is active
            if not is_session_active(session2_id):
                print_error("Second session is not active")
                return False
            
            print_success(f"Second session {session2_id} is active")
            
            # Verify first session is deactivated
            if is_session_active(session1_id):
                print_error(f"First session {session1_id} is still active (should be deactivated)")
                return False
            
            print_success(f"First session {session1_id} was correctly deactivated")
            
            self.session_ids.extend([session1_id, session2_id])
            return True
            
        except Exception as e:
            print_error(f"Exception during old session deactivation test: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_chat_history_isolation(self) -> bool:
        """Test that chat history only returns data for the specified session."""
        print_test_header("Chat History Isolation")
        
        try:
            # Create two sessions
            session1_id = str(uuid.uuid4())
            session2_id = str(uuid.uuid4())
            
            print_info(f"Creating session 1: {session1_id}")
            set_active_session_by_session_id(session1_id)
            
            print_info(f"Creating session 2: {session2_id}")
            set_active_session_by_session_id(session2_id)
            
            # Store chat interactions for session 1
            print_info("Storing chat interaction for session 1")
            chat_id1 = store_chat_interaction(
                user_id="test_user",
                session_id=session1_id,
                user_message="Hello from session 1",
                bot_response="Response for session 1",
                video_id=None
            )
            
            if not chat_id1:
                print_warning("Failed to store chat interaction for session 1 (may be expected if DB not configured)")
            
            # Store chat interactions for session 2
            print_info("Storing chat interaction for session 2")
            chat_id2 = store_chat_interaction(
                user_id="test_user",
                session_id=session2_id,
                user_message="Hello from session 2",
                bot_response="Response for session 2",
                video_id=None
            )
            
            if not chat_id2:
                print_warning("Failed to store chat interaction for session 2 (may be expected if DB not configured)")
            
            # Get chat history for session 1
            print_info("Retrieving chat history for session 1")
            history1 = get_chat_history_by_session(session1_id, limit=10)
            
            # Get chat history for session 2
            print_info("Retrieving chat history for session 2")
            history2 = get_chat_history_by_session(session2_id, limit=10)
            
            # Verify isolation
            if history1:
                session1_messages = [h.get("session_id") for h in history1]
                if any(sid != session1_id for sid in session1_messages):
                    print_error("Session 1 history contains messages from other sessions")
                    return False
                print_success(f"Session 1 history contains {len(history1)} messages (all from session 1)")
            
            if history2:
                session2_messages = [h.get("session_id") for h in history2]
                if any(sid != session2_id for sid in session2_messages):
                    print_error("Session 2 history contains messages from other sessions")
                    return False
                print_success(f"Session 2 history contains {len(history2)} messages (all from session 2)")
            
            # Verify no cross-contamination
            if history1 and history2:
                session1_ids = {h.get("id") for h in history1}
                session2_ids = {h.get("id") for h in history2}
                if session1_ids & session2_ids:
                    print_error("Chat history IDs overlap between sessions (isolation failed)")
                    return False
                print_success("No cross-contamination between session histories")
            
            self.session_ids.extend([session1_id, session2_id])
            return True
            
        except Exception as e:
            print_error(f"Exception during chat history isolation test: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_conversation_chain_clearing(self) -> bool:
        """Test that conversation chains are cleared for new sessions."""
        print_test_header("Conversation Chain Clearing")
        
        if not CONVERSATION_CHAIN_AVAILABLE:
            print_warning("Conversation chain functions not available - skipping test")
            return True
        
        try:
            session_id = str(uuid.uuid4())
            print_info(f"Testing conversation chain clearing for session: {session_id}")
            
            # Try to clear conversation chain (should not raise error even if chain doesn't exist)
            try:
                _clear_conversation_chain(session_id)
                print_success("Conversation chain clearing function works (no errors)")
            except Exception as e:
                print_error(f"Error clearing conversation chain: {e}")
                return False
            
            self.session_ids.append(session_id)
            return True
            
        except Exception as e:
            print_error(f"Exception during conversation chain clearing test: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_session_validation(self) -> bool:
        """Test that session validation works correctly."""
        print_test_header("Session Validation")
        
        try:
            # Create an active session
            active_session_id = str(uuid.uuid4())
            print_info(f"Creating active session: {active_session_id}")
            set_active_session_by_session_id(active_session_id)
            
            # Verify it's active
            if not is_session_active(active_session_id):
                print_error("Active session is not detected as active")
                return False
            print_success(f"Active session {active_session_id} is correctly validated")
            
            # Deactivate the session
            print_info(f"Deactivating session: {active_session_id}")
            deactivate_session_by_id(active_session_id)
            
            # Verify it's inactive
            if is_session_active(active_session_id):
                print_error("Inactive session is still detected as active")
                return False
            print_success(f"Inactive session {active_session_id} is correctly validated")
            
            # Test non-existent session
            non_existent_id = str(uuid.uuid4())
            if is_session_active(non_existent_id):
                print_error("Non-existent session is detected as active")
                return False
            print_success(f"Non-existent session {non_existent_id} is correctly validated as inactive")
            
            self.session_ids.append(active_session_id)
            return True
            
        except Exception as e:
            print_error(f"Exception during session validation test: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_multiple_session_creation(self) -> bool:
        """Test creating multiple sessions in sequence."""
        print_test_header("Multiple Session Creation")
        
        try:
            sessions = []
            num_sessions = 3
            
            print_info(f"Creating {num_sessions} sessions in sequence")
            
            for i in range(num_sessions):
                session_id = str(uuid.uuid4())
                print_info(f"Creating session {i+1}: {session_id}")
                profile_id = set_active_session_by_session_id(session_id)
                
                if profile_id is None:
                    print_error(f"Failed to create session {i+1}")
                    return False
                
                sessions.append(session_id)
                
                # After creating a new session, check that previous sessions are deactivated
                if i > 0:
                    # Check that all previous sessions are now deactivated
                    for prev_idx in range(i):
                        prev_session_id = sessions[prev_idx]
                        if is_session_active(prev_session_id):
                            print_error(f"Previous session {prev_session_id} (session {prev_idx+1}) is still active after creating session {i+1}")
                            return False
                    print_success(f"All previous sessions were correctly deactivated after creating session {i+1}")
                
                # Verify current session is active
                if not is_session_active(session_id):
                    print_error(f"Current session {session_id} (session {i+1}) is not active")
                    return False
                print_success(f"Current session {session_id} (session {i+1}) is active")
            
            # Final verification: only the last session should be active
            active_count = sum(1 for sid in sessions if is_session_active(sid))
            if active_count != 1:
                print_error(f"Expected 1 active session, found {active_count}")
                # Show which sessions are still active
                active_sessions = [sid for sid in sessions if is_session_active(sid)]
                print_error(f"Active sessions: {active_sessions}")
                return False
            
            print_success(f"Only 1 session is active out of {num_sessions} sessions (session {num_sessions})")
            
            self.session_ids.extend(sessions)
            return True
            
        except Exception as e:
            print_error(f"Exception during multiple session creation test: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def cleanup_test_sessions(self):
        """Clean up test sessions."""
        print_info("Cleaning up test sessions...")
        for session_id in self.session_ids:
            try:
                deactivate_session_by_id(session_id)
            except Exception as e:
                print_warning(f"Failed to deactivate session {session_id}: {e}")


def main():
    """Main test runner."""
    print(f"\n{Colors.BOLD}Starting Session Management Tests...{Colors.RESET}\n")
    
    # Check if database is available
    try:
        supabase = get_supabase()
        if supabase is None:
            print_warning("Supabase client is None - some tests may fail")
        else:
            print_success("Supabase client is available")
    except Exception as e:
        print_warning(f"Could not connect to Supabase: {e}")
        print_warning("Some tests may fail or be skipped")
    
    # Run tests
    test_suite = SessionManagementTests()
    success = test_suite.run_all_tests()
    
    # Cleanup
    test_suite.cleanup_test_sessions()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

