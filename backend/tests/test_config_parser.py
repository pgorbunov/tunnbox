import pytest
import tempfile
import os
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.config_parser import ConfigParser


@pytest.fixture
def sample_config():
    return """[Interface]
PrivateKey = cGVyc29uYWxfa2V5X2hlcmU=
Address = 10.0.0.1/24
ListenPort = 51820
DNS = 1.1.1.1
PostUp = iptables -A FORWARD -i %i -j ACCEPT
PostDown = iptables -D FORWARD -i %i -j ACCEPT

[Peer]
PublicKey = cGVlcl9wdWJsaWNfa2V5XzE=
AllowedIPs = 10.0.0.2/32
PersistentKeepalive = 25

[Peer]
PublicKey = cGVlcl9wdWJsaWNfa2V5XzI=
AllowedIPs = 10.0.0.3/32
Endpoint = 192.168.1.100:51820
"""


@pytest.fixture
def temp_config_file(sample_config):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
        f.write(sample_config)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.mark.asyncio
async def test_parse_config(temp_config_file):
    """Test parsing a WireGuard config file."""
    config = await ConfigParser.parse_config(temp_config_file)

    # Check interface section
    assert 'interface' in config
    assert config['interface']['privatekey'] == 'cGVyc29uYWxfa2V5X2hlcmU='
    assert config['interface']['address'] == '10.0.0.1/24'
    assert config['interface']['listenport'] == '51820'
    assert config['interface']['dns'] == '1.1.1.1'

    # Check peers
    assert 'peers' in config
    assert len(config['peers']) == 2

    assert config['peers'][0]['publickey'] == 'cGVlcl9wdWJsaWNfa2V5XzE='
    assert config['peers'][0]['allowedips'] == '10.0.0.2/32'
    assert config['peers'][0]['persistentkeepalive'] == '25'

    assert config['peers'][1]['publickey'] == 'cGVlcl9wdWJsaWNfa2V5XzI='
    assert config['peers'][1]['allowedips'] == '10.0.0.3/32'
    assert config['peers'][1]['endpoint'] == '192.168.1.100:51820'


@pytest.mark.asyncio
async def test_write_config(temp_config_file):
    """Test writing a WireGuard config file."""
    config = {
        'interface': {
            'privatekey': 'dGVzdF9wcml2YXRlX2tleQ==',
            'address': '10.0.0.1/24',
            'listenport': '51820',
        },
        'peers': [
            {
                'publickey': 'dGVzdF9wdWJsaWNfa2V5',
                'allowedips': '10.0.0.2/32',
            }
        ]
    }

    await ConfigParser.write_config(temp_config_file, config)

    # Re-parse and verify
    parsed = await ConfigParser.parse_config(temp_config_file)
    assert parsed['interface']['privatekey'] == 'dGVzdF9wcml2YXRlX2tleQ=='
    assert parsed['interface']['address'] == '10.0.0.1/24'
    assert len(parsed['peers']) == 1
    assert parsed['peers'][0]['publickey'] == 'dGVzdF9wdWJsaWNfa2V5'


@pytest.mark.asyncio
async def test_add_peer_to_config(temp_config_file):
    """Test adding a peer to an existing config."""
    new_peer = {
        'publickey': 'bmV3X3BlZXJfa2V5',
        'allowedips': '10.0.0.4/32',
        'persistentkeepalive': '25',
    }

    await ConfigParser.add_peer_to_config(temp_config_file, new_peer)

    # Re-parse and verify
    config = await ConfigParser.parse_config(temp_config_file)
    assert len(config['peers']) == 3
    assert config['peers'][-1]['publickey'] == 'bmV3X3BlZXJfa2V5'
    assert config['peers'][-1]['allowedips'] == '10.0.0.4/32'


@pytest.mark.asyncio
async def test_remove_peer_from_config(temp_config_file):
    """Test removing a peer from a config."""
    await ConfigParser.remove_peer_from_config(temp_config_file, 'cGVlcl9wdWJsaWNfa2V5XzE=')

    # Re-parse and verify
    config = await ConfigParser.parse_config(temp_config_file)
    assert len(config['peers']) == 1
    assert config['peers'][0]['publickey'] == 'cGVlcl9wdWJsaWNfa2V5XzI='


@pytest.mark.asyncio
async def test_update_peer_in_config(temp_config_file):
    """Test updating a peer in a config."""
    updates = {
        'allowedips': '10.0.0.100/32',
        'persistentkeepalive': '30',
    }

    await ConfigParser.update_peer_in_config(
        temp_config_file,
        'cGVlcl9wdWJsaWNfa2V5XzE=',
        updates
    )

    # Re-parse and verify
    config = await ConfigParser.parse_config(temp_config_file)
    peer = next(p for p in config['peers'] if p['publickey'] == 'cGVlcl9wdWJsaWNfa2V5XzE=')
    assert peer['allowedips'] == '10.0.0.100/32'
    assert peer['persistentkeepalive'] == '30'


def test_normalize_key_for_write():
    """Test key normalization for writing."""
    assert ConfigParser._normalize_key_for_write('privatekey') == 'PrivateKey'
    assert ConfigParser._normalize_key_for_write('publickey') == 'PublicKey'
    assert ConfigParser._normalize_key_for_write('allowedips') == 'AllowedIPs'
    assert ConfigParser._normalize_key_for_write('listenport') == 'ListenPort'
    assert ConfigParser._normalize_key_for_write('persistentkeepalive') == 'PersistentKeepalive'
