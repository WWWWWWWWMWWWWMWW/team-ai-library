"""Pure governance plans; no client-side history rewrite or automatic recall."""
from copy import deepcopy
from .contracts import TeamLibError, validate_version


def plan_withdrawal(state,version,reason):
    validate_version(version)
    if not isinstance(reason,str) or not reason.strip():
        raise TeamLibError('INVALID_PACKAGE','A non-sensitive withdrawal reason is required')
    result=deepcopy(state)
    withdrawn=result.setdefault('withdrawn_versions',[])
    existing=[v.get('version') if isinstance(v,dict) else v for v in withdrawn]
    if version not in existing: withdrawn.append(version)
    if result.get('recommended_version')==version: result['recommended_version']=None
    return result


def recommend_recovery(state,version,available_versions):
    validate_version(version)
    withdrawn=[v.get('version') if isinstance(v,dict) else v for v in state.get('withdrawn_versions',[])]
    if version in withdrawn: raise TeamLibError('WITHDRAWN','Recovery version is withdrawn')
    if version not in available_versions: raise TeamLibError('DEPENDENCY_BLOCKED','Explicit recovery version is missing')
    return dict(state='prepared',version=version,checks_required=['fresh availability and revocations','entire dependency integrity','scope, environment and effects','preserve local changes','actual reuse evidence'],automatic_recall=False,business_rollback_authorized=False)
