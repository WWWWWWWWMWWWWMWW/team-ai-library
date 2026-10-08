"""Deterministic discovery, followed by AI judgement of actual applicability."""
import re
from .dependencies import load_catalog


def search_entries(snapshot,query):
    query=str(query).strip().casefold()
    if not query:return []
    terms=[query]+[x for x in re.split(r'[\s,，;；]+',query) if x and x!=query]
    results=[]
    for (identifier,version),record in load_catalog(snapshot).items():
        meta=record['meta'];state=record['state']
        fields=[meta['title'],meta['summary'],*meta['tags'],*meta['aliases'],identifier]
        score=0
        for term in terms:
            for index,field in enumerate(fields):
                value=field.casefold()
                if term in value:score+=10 if index==0 else 3
                elif len(value)>=2 and value in term:score+=2
        if not score:continue
        withdrawn=version in state['withdrawn_versions']
        recommended=not withdrawn and state['recommended_version']==version
        results.append({'id':identifier,'title':meta['title'],'kind':meta['kind'],
                        'summary':meta['summary'],'tags':meta['tags'],'aliases':meta['aliases'],
                        'version':version,'state':'withdrawn' if withdrawn else 'active',
                        'recommended':recommended,'scope':record['scope'],
                        'compatibility':record['compatibility'],'effects':record['effects'],
                        'manifest_sha256':record['manifest_sha256'],
                        'verification':state['verification'],'score':score})
    return sorted(results,key=lambda row:(not row['recommended'],row['state']=='withdrawn',
                                         -row['score'],row['id'],tuple(-int(x) for x in row['version'].split('.'))))
