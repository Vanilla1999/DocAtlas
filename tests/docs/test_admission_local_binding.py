"""A local default witness must bind the requested subject and property."""
import pytest

from docmancer.docs.application.retrieval_need_support import retrieval_need_local_witness


def default_need(subject='RelayClient', attribute='timeout'):
    return {'query_id': 'need-default', 'query_origin': 'retrieval_need',
            'text': f'What is the default {attribute} of {subject}?',
            'need_subject': subject, 'need_relation': 'default'}































