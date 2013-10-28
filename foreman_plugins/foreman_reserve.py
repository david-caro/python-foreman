DEFS = {'GET': {'hosts_reserve': {
                    'query': {'ptype': 'String', 'required': False},
                    'reason': {'ptype': 'String', 'required': True},
                    'amount': {'ptype': 'Integer', 'required': False}},
                'hosts_release': {
                    'query': {'ptype': 'String', 'required': False},
                    'host_name': {'ptype': 'String', 'required': False},
                    'amount': {'ptype': 'Integer', 'required': False}},
                'show_available': {
                    'query ': {'ptype': 'String', 'required': False},
                    'amount': {'ptype': 'Integer', 'required': False}},
                'show_reserved': {
                    'query': {'ptype': 'String', 'required': False}},
                'update_reserved_reason': {
                    'query': {'ptype': 'String', 'required': False},
                    'reason': {'ptype': 'String', 'required': True},
                    'amount': {'ptype': 'Integer', 'required': False}}}}
