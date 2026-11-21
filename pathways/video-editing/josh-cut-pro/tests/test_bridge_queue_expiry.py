"""Read only the bridge function AST; never import the running helper or its configuration."""
import ast
import queue
import time
import unittest
from pathlib import Path

class QueueExpiry(unittest.TestCase):
    def setUp(self):
        source=(Path(__file__).resolve().parents[1]/'helper'/'dajoshi_cut.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='bridge_poll']
        self.bridge={'queue':queue.Queue(),'waiting':{},'plugin_seen':0,'plugin_info':{}}
        self.ns={'BRIDGE':self.bridge,'time':time,'queue':queue}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'<isolated bridge_poll>','exec'),self.ns)
    def test_expired_and_timed_out_queued_commands_are_skipped(self):
        now=int(time.time()*1000)
        for call in [dict(id='timed-out',expires_at_ms=now+100000),dict(id='expired',expires_at_ms=now-1),dict(id='live',expires_at_ms=now+100000)]:self.bridge['queue'].put(call)
        self.bridge['waiting']={'expired':object(),'live':object()}
        self.assertEqual(self.ns['bridge_poll']({})['id'],'live')
    def test_legacy_live_queue_entry_remains_compatible(self):
        self.bridge['queue'].put(dict(id='live'));self.bridge['waiting']['live']=object()
        self.assertEqual(self.ns['bridge_poll']({})['id'],'live')
    def test_timeout_is_reported_as_unknown_if_already_started(self):
        source=(Path(__file__).resolve().parents[1]/'helper'/'dajoshi_cut.py').read_text(encoding='utf-8')
        self.assertIn('already started may still be running',source)
        self.assertIn('expires_at_ms=int((time.time() + timeout) * 1000)',source)

if __name__=='__main__':unittest.main()
