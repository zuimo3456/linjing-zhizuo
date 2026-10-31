"""Source-bound semantic risk records; client JSON cannot clear a server finding."""
import json,threading,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'data';POLICY='dense-half-second-v1'
_lock=threading.RLock()

def load_review(shot):
    from evidence_store import identity
    from setup_onnx_model import WEIGHT_SHA
    path=DATA/shot['media_id']/'semantic-review.json'
    if not path.is_file():return None
    with _lock:
        try:entry=json.loads(path.read_text(encoding='utf8')).get(shot['id'])
        except (OSError,ValueError,AttributeError):return None
    if entry and entry.get('evidence_id')==identity(shot) and entry.get('policy')==POLICY and entry.get('weights')==WEIGHT_SHA and entry.get('analysis_version')==shot.get('analysis_version'):
        return entry
    return None

def store_review(shot,candidate):
    from evidence_store import identity
    from setup_onnx_model import WEIGHT_SHA
    path=DATA/shot['media_id']/'semantic-review.json'
    path.parent.mkdir(exist_ok=True,parents=True)
    with _lock:
        try:entries=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
        except (OSError,ValueError):entries={}
        entries[shot['id']]={'evidence_id':identity(shot),'policy':POLICY,'weights':WEIGHT_SHA,
                             'analysis_version':shot.get('analysis_version'),'candidate':candidate,'issue':candidate.get('semantic_issue')}
        temporary=path.with_name('semantic-review-'+uuid.uuid4().hex+'.tmp')
        try:temporary.write_text(json.dumps(entries,ensure_ascii=False),encoding='utf8');temporary.replace(path)
        finally:temporary.unlink(missing_ok=True)

def semantic_issue(shot):
    record=load_review(shot)
    return record.get('issue') if record else None
