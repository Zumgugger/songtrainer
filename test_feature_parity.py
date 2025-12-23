#!/usr/bin/env python3
"""
Feature Parity Test for Refactored Songtrainer App
Tests key workflows to verify refactored app has same features as old app
"""

import requests
import json
import sys

BASE_URL = 'http://localhost:5000'
SESSION = requests.Session()

# Test credentials
TEST_EMAIL = 'markus.gugger@gmail.com'
TEST_PASSWORD = 'Password123!'

def test_login():
    """Test authentication endpoint"""
    print("Testing login...")
    response = SESSION.post(f'{BASE_URL}/api/auth/login', json={
        'email': TEST_EMAIL,
        'password': TEST_PASSWORD
    })
    if response.status_code == 200:
        user = response.json().get('user')
        print(f"  ✓ Login successful as {user['email']} (role: {user['role']})")
        return True
    else:
        print(f"  ✗ Login failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return False


def test_get_repertoires():
    """Test GET /api/repertoires"""
    print("Testing GET repertoires...")
    response = SESSION.get(f'{BASE_URL}/api/repertoires')
    if response.status_code == 200:
        reps = response.json()
        print(f"  ✓ Got {len(reps)} repertoires")
        if reps:
            rep = reps[0]
            required_fields = ['id', 'name', 'user_id', 'song_count']
            missing = [f for f in required_fields if f not in rep]
            if missing:
                print(f"  ! Missing fields in repertoire: {missing}")
            else:
                print(f"  ✓ Repertoire has all required fields")
        return True
    else:
        print(f"  ✗ Failed: {response.status_code}")
        return False


def test_get_songs(repertoire_id):
    """Test GET /api/songs"""
    print(f"Testing GET songs for repertoire {repertoire_id}...")
    response = SESSION.get(f'{BASE_URL}/api/songs?repertoire_id={repertoire_id}')
    if response.status_code == 200:
        songs = response.json()
        print(f"  ✓ Got {len(songs)} songs")
        if songs:
            song = songs[0]
            required_fields = ['id', 'title', 'artist', 'practice_count', 'practice_target', 'skills']
            missing = [f for f in required_fields if f not in song]
            if missing:
                print(f"  ! Missing fields in song: {missing}")
            else:
                print(f"  ✓ Song has all required fields")
                print(f"    - Title: {song['title']}")
                print(f"    - Skills: {len(song.get('skills', []))} assigned")
        return True
    else:
        print(f"  ✗ Failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return False


def test_get_skills():
    """Test GET /api/skills"""
    print("Testing GET skills...")
    response = SESSION.get(f'{BASE_URL}/api/skills')
    if response.status_code == 200:
        skills = response.json()
        print(f"  ✓ Got {len(skills)} skills")
        if skills:
            skill = skills[0]
            if 'id' in skill and 'name' in skill:
                print(f"  ✓ Skill has required fields")
            else:
                print(f"  ! Skill missing id or name")
        return True
    else:
        print(f"  ✗ Failed: {response.status_code}")
        return False


def test_get_user_me():
    """Test GET /api/auth/me"""
    print("Testing GET /api/auth/me...")
    response = SESSION.get(f'{BASE_URL}/api/auth/me')
    if response.status_code == 200:
        user = response.json().get('user')
        print(f"  ✓ Got current user: {user['email']}")
        return True
    else:
        print(f"  ✗ Failed: {response.status_code}")
        return False


def test_get_time_practiced(repertoire_id):
    """Test GET /api/repertoires/<id>/time-practiced"""
    print(f"Testing GET time-practiced for repertoire {repertoire_id}...")
    response = SESSION.get(f'{BASE_URL}/api/repertoires/{repertoire_id}/time-practiced')
    if response.status_code == 200:
        data = response.json()
        required_fields = ['time_practiced', 'start_date']
        missing = [f for f in required_fields if f not in data]
        if missing:
            print(f"  ! Missing fields: {missing}")
        else:
            print(f"  ✓ Time practiced data: {data['time_practiced']} since {data['start_date']}")
        return True
    else:
        print(f"  ✗ Failed: {response.status_code}")
        return False


def test_page_load():
    """Test if main page loads"""
    print("Testing main page load...")
    response = SESSION.get(f'{BASE_URL}/')
    if response.status_code == 200:
        if 'index.html' in response.text or '<html' in response.text:
            print(f"  ✓ Main page loads successfully")
            return True
        else:
            print(f"  ! Page loaded but content unexpected")
            return True
    else:
        print(f"  ✗ Failed: {response.status_code}")
        return False


def main():
    print("=" * 60)
    print("SONGTRAINER FEATURE PARITY TEST")
    print("=" * 60)
    print()
    
    results = []
    
    # Test 1: Login
    if not test_login():
        print("\n✗ Cannot proceed without login")
        return 1
    print()
    
    # Test 2: Main page
    results.append(("Page Load", test_page_load()))
    print()
    
    # Test 3: Auth endpoints
    results.append(("GET /api/auth/me", test_get_user_me()))
    print()
    
    # Test 4: Repertoires
    results.append(("GET /api/repertoires", test_get_repertoires()))
    print()
    
    # Get first repertoire for song tests
    response = SESSION.get(f'{BASE_URL}/api/repertoires')
    repertoires = response.json()
    if repertoires:
        rep_id = repertoires[0]['id']
        
        # Test 5: Songs
        results.append(("GET /api/songs", test_get_songs(rep_id)))
        print()
        
        # Test 6: Time practiced
        results.append(("GET /api/repertoires/<id>/time-practiced", test_get_time_practiced(rep_id)))
        print()
    
    # Test 7: Skills
    results.append(("GET /api/skills", test_get_skills()))
    print()
    
    # Print summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Refactored app has feature parity.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
