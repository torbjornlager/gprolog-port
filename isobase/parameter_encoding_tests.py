"""HTTP decoding must reject malformed text before continuation admission."""
import http.client
import json
import os
import select
import subprocess
import urllib.parse


node = subprocess.Popen(
    [os.environ.get('ISO_NODE', './isobase-node'), '--auth', 'open', '--port', '0',
     '--max-queries', '1', '--idle-ms', '30000'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def request(query):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        connection.request('GET', '/call?' + query)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def children():
    lines = subprocess.check_output(['ps', '-axo', 'pid=,ppid='], text=True).splitlines()
    return {int(pid) for pid, parent in (line.split() for line in lines)
            if int(parent) == node.pid}


def escaped(value):
    return ''.join(f'%{byte:02X}' for byte in value)


try:
    assert select.select([node.stdout], [], [], 5)[0], 'node startup timed out'
    port = json.loads(node.stdout.readline())['port']
    continuation = 'goal=between(1,3,X)&limit=1'
    assert request(continuation)[1]['data'] == [{'X': '1'}]
    retained = children()
    assert len(retained) == 1
    invalid = [bytes([byte]) for byte in range(128, 256)]
    invalid += [
        b'\xc0\x80', b'\xc0\xaf', b'\xc1\xbf',  # overlong two-byte forms
        b'\xe0\x80\x80', b'\xe0\x9f\xbf',
        b'\xf0\x80\x80\x80', b'\xf0\x8f\xbf\xbf',
        b'\xed\xa0\x80', b'\xed\xbf\xbf',  # surrogate range
        b'\xf4\x90\x80\x80', b'\xf7\xbf\xbf\xbf',  # above Unicode maximum
        b'\xc2a', b'\xe2\x82a', b'\xf0\x90\x80a',  # wrong continuation
        b'\xe2\x82', b'\xf0\x90', b'\xf0\x90\x80',  # truncated sequences
    ]
    checked = 0
    for value in invalid:
        for field in ('goal', 'template', 'src_text'):
            query = f'{field}={escaped(value)}'
            if field != 'goal':
                query = 'goal=true&' + query
            result = request(query)
            assert result == (400, {'type': 'error', 'data': 'invalid_parameters'}), (query, result)
            checked += 1
    for query in ('goal=%', 'goal=%A', 'goal=%GG', 'goal=%00',
                  'goal=true&%67oal=fail', '%FF=true', 'goal=true&template=%00'):
        assert request(query) == (400, {'type': 'error', 'data': 'invalid_parameters'}), query
    for query in ('goal=true#', 'goal=X%3D%27#%27',
                  'goal=true&template=%27#%27', 'goal=true&src_text=p(%27#%27).'):
        assert request(query) == (400, {'type': 'error', 'data': 'invalid_request_target'}), query
    assert children() == retained, 'invalid parameters evicted the continuation'
    assert request(continuation + '&offset=1')[1]['data'] == [{'X': '2'}]
    assert children() == retained, 'continuation was replayed in a new worker'
    assert request(continuation + '&offset=2')[1]['more'] is False

    # Valid scalar boundaries, spanning all UTF-8 widths, survive decoding.
    for code in (0x7f, 0x80, 0x7ff, 0x800, 0xd7ff, 0xe000, 0xffff,
                 0x10000, 0x10ffff):
        text = chr(code)
        query = urllib.parse.urlencode({'goal': f"atom_codes('{text}',[{code}])"})
        result = request(query)
        assert result == (200, {'type': 'success', 'data': [{}], 'more': False}), (code, result)
    for query in ('goal=atom_codes(%27a%2Bb%27,[97,43,98])',
                  'goal=atom_codes(%27a+b%27,[97,32,98])',
                  'goal=atom_codes(%27%2526%27,[37,50,54])',
                  'goal=atom_codes(%27%23%27,[35])'):
        assert request(query) == (200, {'type': 'success', 'data': [{}], 'more': False}), query
    source = urllib.parse.urlencode({'goal': "p('å😀')", 'src_text': "p('å😀')."})
    assert request(source)[1] == {'type': 'success', 'data': [{}], 'more': False}
    # Empty form fields remain ignored, while explicit empty optional source
    # is valid. Separators do not become data and escapes are decoded once.
    for query in ('&goal=true', 'goal=true&', 'goal=true&&src_text='):
        assert request(query) == (200, {'type': 'success', 'data': [{}], 'more': False}), query
    print(f'PASS parameter encoding: {checked} UTF-8 rejections, escapes, Unicode and continuation preservation')
finally:
    node.terminate()
    try:
        node.wait(timeout=5)
    except subprocess.TimeoutExpired:
        node.kill()
        node.wait()
        raise
    assert node.returncode == 0, (node.returncode, node.stderr.read())
    assert not node.stderr.read()
