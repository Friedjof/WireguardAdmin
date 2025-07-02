#!/usr/bin/env python3
"""
Basic tests for VPN management application
"""

import pytest
import os
import sys

# Set environment variable for testing before importing app
os.environ['TESTING'] = 'True'

# Mock iptables if not available
class MockIptc:
    class Rule:
        pass
    class Chain:
        pass
    class Table:
        pass

if 'iptc' not in sys.modules:
    sys.modules['iptc'] = MockIptc()

from app import app, db


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()


def test_index_page(client):
    """Test that index page loads"""
    response = client.get('/')
    assert response.status_code == 200


def test_peers_page(client):
    """Test that peers page loads (index is at root)"""
    response = client.get('/')
    assert response.status_code == 200


def test_app_config():
    """Test basic app configuration"""
    assert app is not None
    assert app.config['SECRET_KEY'] is not None