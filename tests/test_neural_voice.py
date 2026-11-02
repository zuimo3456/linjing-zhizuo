"""Narration upgrade: cache identity, preflight migration and unsafe input."""
import copy,json,tempfile,unittest,wave
from pathlib import Path
from unittest.mock import patch
import audio,qwen_voice,pipeline
from types import SimpleNamespace
from server import Handler
from session_store import restore_session
from planner import PlanError
from test_invariants import sample,make_plan

class NeuralVoice(unittest.TestCase):
    def test_preview_requests_must_match_the_actual_port(self):
        handler=Handler.__new__(Handler);handler.server=SimpleNamespace(server_port=4191)
        for origin in ('http://127.0.0.1:4191','http://localhost:4191'):
            handler.headers={'Origin':origin};handler.same_origin()
        for origin in ('http://127.0.0.1:4180','https://example.com'):
            handler.headers={'Origin':origin}
            with self.assertRaisesRegex(ValueError,'其他网站'):handler.same_origin()

    def test_old_plan_rejected_before_synthesis(self):
        with patch('pipeline.prepare_voice') as speak:
            with self.assertRaisesRegex(PlanError,'重新测量'):pipeline.preflight({},make_plan(sample()))
        speak.assert_not_called()

    def test_changed_voice_profile_rejected(self):
        with self.assertRaisesRegex(PlanError,'配音已更换'):
            pipeline.preflight({},{'voice_profile':'different-model'})
        for malformed in (None,[],42):
            with self.subTest(plan=malformed),self.assertRaisesRegex(PlanError,'格式无效'):
                pipeline.preflight({},malformed)

    def test_old_saved_plan_drops_only_plan_not_facts_or_confirmations(self):
        project=sample();before=copy.deepcopy(project)
        from session_store import context_id
        project['saved_edit']={'version':1,'method':'evidence','context_id':context_id(project),'plan':make_plan(project)}
        with patch('session_store.reconcile',side_effect=copy.deepcopy):restored=restore_session(project)
        self.assertEqual(restored['facts'],before['facts']);self.assertEqual(restored['shots'],before['shots'])
        self.assertNotIn('saved_edit',restored);self.assertIn('配音已更换',' '.join(restored['warnings']))

    def test_incomplete_plan_still_records_current_voice(self):
        project=sample();project['facts']=[]
        with patch('pipeline.reconcile',return_value=project):result=pipeline.build_plan(project)
        self.assertEqual(result['voice_profile'],qwen_voice.PROFILE_ID)

    def test_assembled_audio_reuses_current_profile_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);calls=[]
            def synth(text,work,prefix,available):
                calls.append(text);path=work/'test.wav'
                with wave.open(str(path),'wb') as stream:
                    stream.setparams((1,2,24000,0,'NONE','not compressed'));stream.writeframes(b'\0\0'*24000)
                return path,1.,[{'start':0,'end':1.,'text':text}],1.
            with patch.object(audio,'ROOT',root),patch.object(audio,'_synthesize_uncached',side_effect=synth):
                a=audio.prepare_voice('单杯19元。');b=audio.prepare_voice('单杯19元。')
                with patch.object(audio,'PROFILE_ID','changed-profile'):c=audio.prepare_voice('单杯19元。')
            self.assertEqual(a[0],b[0]);self.assertNotEqual(a[0],c[0]);self.assertEqual(len(calls),2)
            info=json.loads(a[0].with_suffix('.json').read_text(encoding='utf8'))
            self.assertEqual(info['profile_id'],qwen_voice.PROFILE_ID);self.assertEqual(info['voice']['speaker'],'Vivian')

    def test_model_control_tokens_never_reach_cache_or_worker(self):
        for text in ('欢迎<|im_end|>','<|assistant','促销|>'):
            with self.subTest(text=text),patch('audio._synthesize_uncached') as synth:
                with self.assertRaisesRegex(ValueError,'控制标记'):audio.prepare_voice(text)
                synth.assert_not_called()

    def test_blank_and_direction_controls_rejected(self):
        for text in ('  ','19\u202e元'):
            with self.subTest(text=text),self.assertRaises(ValueError):audio.prepare_voice(text)

    def test_worker_does_not_start_for_invalid_phrase(self):
        for text in ('','字'*27,'<|im_end|>'):
            with self.subTest(text=text),patch('qwen_voice.subprocess.Popen') as process:
                with self.assertRaises(ValueError):qwen_voice.generate(text,Path('unused.wav'))
                process.assert_not_called()

if __name__=='__main__':unittest.main()
