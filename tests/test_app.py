"""
Comprehensive tests for the Mergington High School Activities API.

Uses FastAPI TestClient with AAA (Arrange-Act-Assert) pattern.
Tests cover all endpoints: GET /activities, POST signup, DELETE signup.
Includes success paths and edge cases (duplicates, missing activities, etc.).
"""

import pytest
from copy import deepcopy
from fastapi.testclient import TestClient
from src.app import app, activities as original_activities


@pytest.fixture
def client():
    """Provide a TestClient for making requests to the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def fresh_activities(monkeypatch):
    """
    Provide fresh activity data for each test.
    
    This fixture creates a deep copy of the original activities
    and patches the app's activities dict to use the copy.
    This prevents test state pollution between tests.
    """
    activities_copy = deepcopy(original_activities)
    monkeypatch.setattr("src.app.activities", activities_copy)
    return activities_copy


class TestGetActivities:
    """Tests for the GET /activities endpoint."""
    
    def test_get_activities_returns_all_activities(self, client, fresh_activities):
        """
        GIVEN: The API server is running
        WHEN: A GET request is made to /activities
        THEN: The response includes all available activities
        """
        # Act
        response = client.get("/activities")
        
        # Assert
        assert response.status_code == 200
        activities = response.json()
        assert len(activities) > 0
        assert "Chess Club" in activities
        assert "Programming Class" in activities
        assert "Gym Class" in activities
    
    def test_get_activities_has_correct_structure(self, client, fresh_activities):
        """
        GIVEN: The GET /activities endpoint
        WHEN: A request is made
        THEN: Each activity has required fields: description, schedule, max_participants, participants
        """
        # Act
        response = client.get("/activities")
        activities = response.json()
        
        # Assert
        for activity_name, activity_data in activities.items():
            assert isinstance(activity_name, str)
            assert "description" in activity_data
            assert "schedule" in activity_data
            assert "max_participants" in activity_data
            assert isinstance(activity_data["max_participants"], int)
            assert "participants" in activity_data
            assert isinstance(activity_data["participants"], list)
    
    def test_get_activities_participants_are_emails(self, client, fresh_activities):
        """
        GIVEN: The API with activities that have participants
        WHEN: A GET request is made to /activities
        THEN: All participants are strings (emails)
        """
        # Act
        response = client.get("/activities")
        activities = response.json()
        
        # Assert
        for activity_data in activities.values():
            for participant in activity_data["participants"]:
                assert isinstance(participant, str)
                assert "@" in participant  # Basic email validation


class TestSignupForActivity:
    """Tests for the POST /activities/{activity_name}/signup endpoint."""
    
    def test_signup_success(self, client, fresh_activities):
        """
        GIVEN: An activity exists with available spots
        WHEN: A student signs up with a new email
        THEN: The signup is successful and returns a success message
        """
        # Arrange
        activity_name = "Chess Club"
        email = "newstudent@mergington.edu"
        
        # Act
        response = client.post(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        
        # Assert
        assert response.status_code == 200
        assert "Signed up" in response.json()["message"]
        assert email in response.json()["message"]
    
    def test_signup_adds_participant_to_activity(self, client, fresh_activities):
        """
        GIVEN: An activity with initial participants
        WHEN: A new student signs up
        THEN: The student is added to the activity's participant list
        """
        # Arrange
        activity_name = "Chess Club"
        email = "newstudent@mergington.edu"
        initial_count = len(fresh_activities[activity_name]["participants"])
        
        # Act
        client.post(f"/activities/{activity_name}/signup", params={"email": email})
        
        # Assert
        updated_activities = client.get("/activities").json()
        assert len(updated_activities[activity_name]["participants"]) == initial_count + 1
        assert email in updated_activities[activity_name]["participants"]
    
    def test_signup_duplicate_fails(self, client, fresh_activities):
        """
        GIVEN: A student already signed up for an activity (tests the bug fix)
        WHEN: The same student tries to sign up again
        THEN: The signup fails with a 400 error
        """
        # Arrange
        activity_name = "Chess Club"
        email = "michael@mergington.edu"  # Already in Chess Club
        
        # Act
        response = client.post(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        
        # Assert
        assert response.status_code == 400
        assert "already signed up" in response.json()["detail"]
    
    def test_signup_duplicate_does_not_add_duplicate(self, client, fresh_activities):
        """
        GIVEN: A student already signed up for an activity
        WHEN: An attempt is made to sign them up again
        THEN: The participant list is not modified (no duplicate entry)
        """
        # Arrange
        activity_name = "Chess Club"
        email = "michael@mergington.edu"
        initial_count = len(fresh_activities[activity_name]["participants"])
        
        # Act
        client.post(f"/activities/{activity_name}/signup", params={"email": email})
        
        # Assert
        updated_activities = client.get("/activities").json()
        # Count occurrences of the email in participants
        occurrences = updated_activities[activity_name]["participants"].count(email)
        assert occurrences == 1  # Only one entry, no duplicates
    
    def test_signup_activity_not_found(self, client, fresh_activities):
        """
        GIVEN: A signup request for a non-existent activity
        WHEN: The request is made with an invalid activity name
        THEN: The API returns a 404 error
        """
        # Arrange
        activity_name = "NonExistent Club"
        email = "student@mergington.edu"
        
        # Act
        response = client.post(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        
        # Assert
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_signup_with_url_encoded_activity_name(self, client, fresh_activities):
        """
        GIVEN: An activity with special characters or spaces in its name
        WHEN: A student signs up using the properly encoded activity name
        THEN: The signup succeeds
        """
        # Arrange
        activity_name = "Programming Class"
        encoded_name = "Programming%20Class"
        email = "coder@mergington.edu"
        
        # Act
        response = client.post(
            f"/activities/{encoded_name}/signup",
            params={"email": email}
        )
        
        # Assert
        assert response.status_code == 200
    
    def test_signup_multiple_students_same_activity(self, client, fresh_activities):
        """
        GIVEN: An activity and multiple different students
        WHEN: Different students sign up for the same activity
        THEN: All signups succeed and the participant count increases
        """
        # Arrange
        activity_name = "Gym Class"
        emails = ["student1@mergington.edu", "student2@mergington.edu", "student3@mergington.edu"]
        initial_count = len(fresh_activities[activity_name]["participants"])
        
        # Act
        for email in emails:
            response = client.post(
                f"/activities/{activity_name}/signup",
                params={"email": email}
            )
            assert response.status_code == 200
        
        # Assert
        updated_activities = client.get("/activities").json()
        assert len(updated_activities[activity_name]["participants"]) == initial_count + len(emails)


class TestUnregisterFromActivity:
    """Tests for the DELETE /activities/{activity_name}/signup endpoint."""
    
    def test_unregister_success(self, client, fresh_activities):
        """
        GIVEN: A student is signed up for an activity
        WHEN: A DELETE request is made to unregister them
        THEN: The unregistration is successful
        """
        # Arrange
        activity_name = "Chess Club"
        email = "michael@mergington.edu"
        
        # Act
        response = client.delete(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        
        # Assert
        assert response.status_code == 200
        assert "Unregistered" in response.json()["message"]
    
    def test_unregister_removes_participant(self, client, fresh_activities):
        """
        GIVEN: A student in an activity's participant list
        WHEN: They are unregistered via DELETE
        THEN: They are removed from the participant list
        """
        # Arrange
        activity_name = "Chess Club"
        email = "michael@mergington.edu"
        initial_count = len(fresh_activities[activity_name]["participants"])
        
        # Act
        client.delete(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        
        # Assert
        updated_activities = client.get("/activities").json()
        assert len(updated_activities[activity_name]["participants"]) == initial_count - 1
        assert email not in updated_activities[activity_name]["participants"]
    
    def test_unregister_not_found_fails(self, client, fresh_activities):
        """
        GIVEN: A student who is NOT signed up for an activity
        WHEN: A DELETE request is made to unregister them
        THEN: The request fails with a 400 error
        """
        # Arrange
        activity_name = "Chess Club"
        email = "notstudent@mergington.edu"  # Not in Chess Club
        
        # Act
        response = client.delete(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        
        # Assert
        assert response.status_code == 400
        assert "not signed up" in response.json()["detail"]
    
    def test_unregister_activity_not_found(self, client, fresh_activities):
        """
        GIVEN: An unregister request for a non-existent activity
        WHEN: The request is made with an invalid activity name
        THEN: The API returns a 404 error
        """
        # Arrange
        activity_name = "Nonexistent Activity"
        email = "student@mergington.edu"
        
        # Act
        response = client.delete(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        
        # Assert
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_unregister_then_signup_again(self, client, fresh_activities):
        """
        GIVEN: A student who previously signed up for an activity
        WHEN: They unregister and then sign up again
        THEN: Both operations succeed
        """
        # Arrange
        activity_name = "Programming Class"
        email = "student@mergington.edu"
        
        # Act - First signup
        response1 = client.post(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        assert response1.status_code == 200
        
        # Act - Unregister
        response2 = client.delete(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        assert response2.status_code == 200
        
        # Act - Sign up again
        response3 = client.post(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        
        # Assert
        assert response3.status_code == 200
        updated_activities = client.get("/activities").json()
        assert email in updated_activities[activity_name]["participants"]
    
    def test_unregister_multiple_from_same_activity(self, client, fresh_activities):
        """
        GIVEN: Multiple students signed up for an activity
        WHEN: Multiple students are unregistered
        THEN: Each unregistration succeeds and participant count decreases correctly
        """
        # Arrange
        activity_name = "Drama Club"
        emails = ["lucas@mergington.edu", "maya@mergington.edu"]
        initial_count = len(fresh_activities[activity_name]["participants"])
        
        # Act
        for email in emails:
            response = client.delete(
                f"/activities/{activity_name}/signup",
                params={"email": email}
            )
            assert response.status_code == 200
        
        # Assert
        updated_activities = client.get("/activities").json()
        assert len(updated_activities[activity_name]["participants"]) == initial_count - len(emails)
        for email in emails:
            assert email not in updated_activities[activity_name]["participants"]


class TestIntegrationScenarios:
    """Integration tests combining multiple operations."""
    
    def test_full_signup_unregister_flow(self, client, fresh_activities):
        """
        GIVEN: The activities API
        WHEN: A student signs up, activity is viewed, then student unregisters
        THEN: All operations succeed and state is consistent
        """
        # Arrange
        activity_name = "Art Club"
        email = "artist@mergington.edu"
        
        # Act & Assert - Sign up
        signup_response = client.post(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        assert signup_response.status_code == 200
        
        # Act & Assert - Verify in activities list
        activities = client.get("/activities").json()
        assert email in activities[activity_name]["participants"]
        
        # Act & Assert - Unregister
        unregister_response = client.delete(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        assert unregister_response.status_code == 200
        
        # Act & Assert - Verify removed from list
        activities = client.get("/activities").json()
        assert email not in activities[activity_name]["participants"]
    
    def test_concurrent_student_signups(self, client, fresh_activities):
        """
        GIVEN: An activity with available spots
        WHEN: Multiple students sign up for the same activity
        THEN: All signups succeed without duplicates
        """
        # Arrange
        activity_name = "Science Club"
        emails = [
            "scientist1@mergington.edu",
            "scientist2@mergington.edu",
            "scientist3@mergington.edu",
            "scientist4@mergington.edu",
        ]
        
        # Act
        for email in emails:
            response = client.post(
                f"/activities/{activity_name}/signup",
                params={"email": email}
            )
            assert response.status_code == 200
        
        # Assert - Verify all are registered exactly once
        activities = client.get("/activities").json()
        participants = activities[activity_name]["participants"]
        for email in emails:
            count = participants.count(email)
            assert count == 1, f"Expected {email} to appear once, but appeared {count} times"
"""
Comprehensive tests for the Mergington High School Activities API

Tests cover all endpoints with both success paths and edge cases,
using the AAA (Arrange-Act-Assert) pattern for clarity.
"""

import copy
import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a FastAPI TestClient for making requests"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to original state before each test"""
    original_activities = copy.deepcopy(activities)
    yield
    # Reset after test
    activities.clear()
    activities.update(original_activities)


# ==================== GET /activities Tests ====================

def test_get_activities_returns_all_activities(client, reset_activities):
    """Test that GET /activities returns all available activities"""
    # Arrange
    # Activities are pre-populated in app.py
    
    # Act
    response = client.get("/activities")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert len(data) > 0
    assert "Chess Club" in data
    assert "Programming Class" in data


def test_get_activities_response_structure(client, reset_activities):
    """Test that activity response has correct structure"""
    # Arrange
    
    # Act
    response = client.get("/activities")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    
    for activity_name, details in data.items():
        assert isinstance(activity_name, str)
        assert isinstance(details, dict)
        assert "description" in details
        assert "schedule" in details
        assert "max_participants" in details
        assert "participants" in details
        assert isinstance(details["participants"], list)


def test_get_activities_participants_are_emails(client, reset_activities):
    """Test that participants list contains email addresses"""
    # Arrange
    
    # Act
    response = client.get("/activities")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    
    for activity_name, details in data.items():
        for participant in details["participants"]:
            assert "@" in participant
            assert isinstance(participant, str)


# ==================== POST /activities/{activity_name}/signup Tests ====================

def test_signup_success_new_participant(client, reset_activities):
    """Test successful signup for a student not yet registered"""
    # Arrange
    activity_name = "Chess Club"
    email = "newstudent@mergington.edu"
    initial_count = len(activities[activity_name]["participants"])
    
    # Act
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    
    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == f"Signed up {email} for {activity_name}"
    assert email in activities[activity_name]["participants"]
    assert len(activities[activity_name]["participants"]) == initial_count + 1


def test_signup_duplicate_prevents_double_registration(client, reset_activities):
    """Test that duplicate signup is rejected"""
    # Arrange
    activity_name = "Chess Club"
    email = "michael@mergington.edu"  # Already registered
    
    # Act
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    
    # Assert
    assert response.status_code == 400
    assert "already signed up" in response.json()["detail"].lower()


def test_signup_activity_not_found(client, reset_activities):
    """Test that signup for non-existent activity returns 404"""
    # Arrange
    activity_name = "Non Existent Activity"
    email = "student@mergington.edu"
    
    # Act
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    
    # Assert
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_signup_multiple_students_same_activity(client, reset_activities):
    """Test that multiple different students can signup for same activity"""
    # Arrange
    activity_name = "Programming Class"
    emails = ["student1@mergington.edu", "student2@mergington.edu", "student3@mergington.edu"]
    
    # Act & Assert for each student
    for email in emails:
        response = client.post(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        assert response.status_code == 200
        assert email in activities[activity_name]["participants"]


def test_signup_url_encoded_activity_name(client, reset_activities):
    """Test signup with special characters in activity name"""
    # Arrange
    activity_name = "Science Club"
    email = "scientist@mergington.edu"
    
    # Act
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    
    # Assert
    assert response.status_code == 200
    assert email in activities[activity_name]["participants"]


# ==================== DELETE /activities/{activity_name}/signup Tests ====================

def test_delete_participant_success(client, reset_activities):
    """Test successful removal of a participant"""
    # Arrange
    activity_name = "Chess Club"
    email = "michael@mergington.edu"  # Already in participants
    initial_count = len(activities[activity_name]["participants"])
    assert email in activities[activity_name]["participants"]
    
    # Act
    response = client.delete(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    
    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == f"Unregistered {email} from {activity_name}"
    assert email not in activities[activity_name]["participants"]
    assert len(activities[activity_name]["participants"]) == initial_count - 1


def test_delete_participant_not_signed_up(client, reset_activities):
    """Test that deleting a non-participant returns error"""
    # Arrange
    activity_name = "Chess Club"
    email = "notstudent@mergington.edu"
    
    # Act
    response = client.delete(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    
    # Assert
    assert response.status_code == 400
    assert "not signed up" in response.json()["detail"].lower()


def test_delete_activity_not_found(client, reset_activities):
    """Test that deleting from non-existent activity returns 404"""
    # Arrange
    activity_name = "Fake Activity"
    email = "student@mergington.edu"
    
    # Act
    response = client.delete(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    
    # Assert
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_then_signup_same_activity(client, reset_activities):
    """Test that a student can signup again after being removed"""
    # Arrange
    activity_name = "Chess Club"
    email = "michael@mergington.edu"
    
    # Act
    # First delete
    delete_response = client.delete(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    assert delete_response.status_code == 200
    assert email not in activities[activity_name]["participants"]
    
    # Then signup again
    signup_response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    
    # Assert
    assert signup_response.status_code == 200
    assert email in activities[activity_name]["participants"]


def test_delete_multiple_participants_same_activity(client, reset_activities):
    """Test removing multiple participants from same activity"""
    # Arrange
    activity_name = "Drama Club"
    emails_to_remove = ["lucas@mergington.edu", "maya@mergington.edu"]
    
    # Act & Assert for each removal
    for email in emails_to_remove:
        response = client.delete(
            f"/activities/{activity_name}/signup",
            params={"email": email}
        )
        assert response.status_code == 200
        assert email not in activities[activity_name]["participants"]


# ==================== Integration Tests ====================

def test_complete_signup_workflow(client, reset_activities):
    """Test complete workflow: signup, view, delete"""
    # Arrange
    activity_name = "Gym Class"
    email = "athlete@mergington.edu"
    
    # Act: Signup
    signup_response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    assert signup_response.status_code == 200
    
    # Act: Verify in activities list
    get_response = client.get("/activities")
    assert get_response.status_code == 200
    assert email in get_response.json()[activity_name]["participants"]
    
    # Act: Delete
    delete_response = client.delete(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    assert delete_response.status_code == 200
    
    # Assert: Verify removed from list
    final_response = client.get("/activities")
    assert email not in final_response.json()[activity_name]["participants"]


def test_root_redirects_to_static(client):
    """Test that root path redirects to static index"""
    # Act
    response = client.get("/", follow_redirects=False)
    
    # Assert
    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"
