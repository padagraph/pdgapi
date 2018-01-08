


# Routes
    
def get_routes(app, host):
    """ list routes of the app """
    routes = []
            
    for rule in app.url_map.iter_rules():
        #raise ValueError('e')
        routes.append({
            'path': rule.rule,
            'url':  host + rule.rule,
            'name': rule.endpoint,
            'methods': list(rule.methods),
            'doc' : app.view_functions[rule.endpoint].__doc__
        })
        routes.sort( key=lambda e: e['url'] )
        # filters api /graph/ and /xplor
    return routes


def get_engines_routes(app, host):
    routes = get_routes(app, host)
    allowed = [ '/xplor/']
    
    def _match(path) :
        path = r['path']
        return any( [ e in path for e in allowed ] ) \
           and not any( ( path.endswith("/play"), path.endswith("/options"), )  )
           
    routes = [ r for r in routes if _match(r) ]
    key = lambda e : e['path'][e['path'].rindex('/')+1:]
    routes = { key(v) : v  for v in routes }
    return routes