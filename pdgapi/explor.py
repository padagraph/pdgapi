#-*- coding:utf-8 -*-

from reliure.web import ReliureAPI, EngineView
from reliure.pipeline import Optionable, Composable
from reliure.types import GenericType
from reliure.engine import Engine

from cello.clustering import export_clustering

import igraph




def igraph2dict(graph, exclude_gattrs=[], exclude_vattrs=[], exclude_eattrs=[], id_attribute=None):
    """ Transform a graph (igraph graph) to a dictionary
    to send it to template (or json)
    
    :param graph: the graph to transform
    :type graph: :class:`igraph.Graph`
    :param exclude_gattrs: graph attributes to exclude (TODO)
    :param exclude_vattrs: vertex attributes to exclude (TODO)
    :param exclude_eattrs: edges attributes to exclude (TODO)
    """
    
    # some check
    assert isinstance(graph, igraph.Graph)
    if 'id' in graph.vs.attributes():
        raise ValueError("The graph already have a vertex attribute 'id'")

    # create the graph dict
    attrs = { k : graph[k] for k in graph.attributes()}
    d = {}
    d['vs'] = []
    d['es'] = []
    
    # attributs of the graph
    if 'nodetypes' in attrs : 
        d['nodetypes']  = attrs.pop('nodetypes')
    if 'edgetypes' in attrs : 
        d['edgetypes']  = attrs.pop('edgetypes')
    
    if 'properties' in attrs:
        d['properties'] = attrs.pop('properties', {})

    if 'meta' in attrs:
        d['meta'] = attrs.pop('meta', {})
        d['meta'].update( {
            'directed' : graph.is_directed(), 
            'bipartite' : 'type' in graph.vs and graph.is_bipartite(),
            'e_attrs' : sorted(graph.es.attribute_names()),
            'v_attrs' : sorted( [ attr for attr in graph.vs.attribute_names() if not attr.startswith('_')])
            })

    # vertices
    v_idx = { }
    for vid, vtx in enumerate(graph.vs):
        vertex = vtx.attributes()
        if id_attribute is not None:
            v_idx[vid] = vertex[id_attribute]
        else:
            v_idx[vid] = vid
            vertex["id"] = vid

        d['vs'].append(vertex)

    # edges
    _getvid = lambda vtxid : v_idx[vtxid] if id_attribute else vtxid 

    for edg in graph.es:
        edge = edg.attributes() # recopie tous les attributs
        edge["source"] = v_idx[edg.source] # match with 'id' vertex attributs
        edge["target"] = v_idx[edg.target]
        #TODO check il n'y a pas de 's' 't' dans attr
        d['es'].append(edge)

    return d

def prepare_graph(graph):

    #if 'doc' in graph.vs.attribute_names():
        #del graph.vs['doc']

    if 'nodetype' not in graph.vs.attribute_names():
        graph.vs['nodetype'] = [ "T" for e in graph.vs ]
    if 'uuid' not in graph.vs.attribute_names():
        graph.vs['uuid'] = range(len(graph.vs))
    if 'properties' not in graph.vs.attribute_names():
        props = [ {  }  for i in range(len(graph.vs))]
        attrs = graph.vs.attribute_names()
        
        for p,v  in zip(props, graph.vs):
            for e in attrs:
                if e not in ['nodetype', 'uuid', 'properties' ]  :
                    p[e] = v[e]
            if 'label' not in attrs:
                p['label']  = v.index
                
        graph.vs['properties'] = props
            

    if 'edgetype' not in graph.es.attribute_names():
        graph.es['edgetype'] = [ "T" for e in graph.es ]
    if 'uuid' not in graph.es.attribute_names():
        graph.es['uuid'] = range(len(graph.es))
    if 'properties' not in graph.es.attribute_names():
        props = [ {  }  for i in range(len(graph.es))]
        attrs = graph.es.attribute_names()
        
        for p,v  in zip(props, graph.es):
            for e in attrs:
                if e not in ['edgetype', 'uuid', 'properties' ]  :
                    p[e] = v[e]
            if 'label' not in attrs:
                p['label']  = v.index
                
        graph.es['properties'] = props

    if 'weight' not in graph.es.attribute_names():
        graph.es['weight'] = [1. for e in graph.es ]

    return graph


def export_graph(graph, exclude_gattrs=[], exclude_vattrs=[], exclude_eattrs=[], id_attribute=None):
    return  igraph2dict(graph, exclude_gattrs, exclude_vattrs, exclude_eattrs, id_attribute)    

    
def QueryUnit(**kwargs):
    default = {
        "query" : "jouer"
    }
    default.update(kwargs)

    return default


class ComplexQuery(GenericType):
    """ Tmuse query type, basicly a list of :class:`QueryUnit`

    >>> qtype = ComplexQuery()
    """
    def parse(self, data):

        graph = data.get('graph', None)
        if not graph:
            raise ValueError("One query should concern one graph")
        data["units"] = [ q['query'] for q in data.get('units', []) ]
        return data

    @staticmethod
    def serialize(complexquery):
        return complexquery

class EdgeList(GenericType):
    def parse(self, data):
        gid = data.get('graph', None)
        edgelist = data.get('edgelist', None)

        if gid is None :
            raise ValueError('graph should not be null')
        if edgelist is None :
            raise ValueError('edgelist should not be null')

        return data

class NodeExpandQuery(GenericType):
    def parse(self, data):
        gid = data.get('graph', None)
        nodes_uuid = data.get('nodes', None)
        weights = data.get('weights', [])

        if gid is None :
            raise ValueError('graph should not be null')
        if nodes_uuid is None :
            raise ValueError('nodes should not be null')

        if len(weights) and len(weights) != len(nodes_uuid):
            raise ValueError("weights and nodes should have same length. %s/%s" % (len(weights), len(nodes_uuid)))

        return data

class AdditiveNodes(GenericType):
    def parse(self, data):
        gid = data.get('graph', None)
        nodes = data.get('nodes', None)
        add = data.get('add', None)

        if gid is None :
            raise ValueError('graph should not be null')
        if nodes is None :
            raise ValueError('nodes should not be null')
        if add is None :
            raise ValueError('add should not be null')

        return data

# Layouts
def layout_api(engines, api=None, optionables=None, prefix="layout"):
        
    def export_layout(graph, layout):
        uuids = graph.vs['uuid']
        coords = { uuid: layout[i] for i,uuid in enumerate(uuids)  }
        return {
            "desc"  : str(layout),
            "coords": coords
        }


    def layout_engine(layouts):
        """ Return a default engine over a lexical graph 
        """
        # setup
        engine = Engine("gbuilder", "layout", "export")
        engine.gbuilder.setup(in_name="request", out_name="graph", hidden=True)
        engine.layout.setup(in_name="graph", out_name="layout")
        engine.export.setup(in_name=["graph", "layout"], out_name="layout", hidden=True)
        
        engine.gbuilder.set(engines.edge_subgraph) 

        for k,v in layouts:
            v.name = k
            
        layouts = [ l for n,l in layouts ]        
        engine.layout.set( *layouts )        
        engine.export.set( export_layout )

        return engine

    from cello.layout.simple import KamadaKawaiLayout, GridLayout, FruchtermanReingoldLayout
    from cello.layout.proxlayout import ProxLayoutPCA, ProxLayoutRandomProj, ProxLayoutMDS, ProxMDSSugiyamaLayout
    from cello.layout.transform import Shaker
    from cello.layout.transform import ByConnectedComponent
    #from cello.layout.simple import DrlLayout

    LAYOUTS = [
        # 3D
        ("3DKamadaKawai" , KamadaKawaiLayout(dim=3) ),
        ("3DMds"         , ProxLayoutMDS(dim=3) | Shaker(kelastic=.9) ),
        ("3DPca"         , ProxLayoutPCA(dim=3, ) | Shaker(kelastic=.9) ),
        ("3DPcaWeighted" , ProxLayoutPCA(dim=3, weighted=True) | Shaker(kelastic=.9) ),
        ("3DRandomProj"  , ProxLayoutRandomProj(dim=3) ),
        ("3DOrdered"     , ProxMDSSugiyamaLayout(dim=3) | Shaker(kelastic=0.9) ),
        # 2D
        ("2DPca"         , ProxLayoutPCA(dim=2) | Shaker(kelastic=1.8) ),
        ("2DMds"         , ProxLayoutMDS(dim=2 ) | Shaker(kelastic=.9) ),
        ("2DKamadaKawai" , KamadaKawaiLayout(dim=2) ),
        # tree
        #("DrlLayout" , DrlLayout(dim=2) ),
        ("2DFruchtermanReingoldLayoutWeighted" , FruchtermanReingoldLayout(dim=2, weighted=True) ),
        ("3DFruchtermanReingoldLayoutWeighted" , FruchtermanReingoldLayout(dim=3, weighted=True) ),
    ]

    
    if api is None:
        api = ReliureAPI(name,expose_route = False)
    if optionables == None : optionables = LAYOUTS
    
    view = EngineView(layout_engine(optionables))
    view.set_input_type(EdgeList())
    view.add_output("layout", lambda x:x)

    api.register_view(view, url_prefix=prefix)
    return api


# Clusters
def clustering_api(engines, api=None, optionables=None, prefix="clustering"):
        
    def clustering_engine(optionables):
        """ Return a default engine over a lexical graph
        """
        # setup
        engine = Engine("gbuilder", "clustering")
        engine.gbuilder.setup(in_name="request", out_name="graph", hidden=True)
        engine.clustering.setup(in_name="graph", out_name="clusters")
        #engine.labelling.setup(in_name="clusters", out_name="clusters", hidden=True)

        engine.gbuilder.set(engines.edge_subgraph) 
        engine.clustering.set(*optionables)

        ## Labelling
        from cello.clustering.labelling.model import Label
        from cello.clustering.labelling.basic import VertexAsLabel, TypeFalseLabel, normalize_score_max

        def _labelling(graph, cluster, vtx):
            return  Label(vtx["uuid"], score=1, role="default")
        
        #labelling = VertexAsLabel( _labelling ) | normalize_score_max
        #engine.labelling.set(labelling)

        return engine
        
    if api is None:
        api = ReliureAPI(name,expose_route = False)
        
    ## Clustering
    from cello.graphs.transform import EdgeAttr
    from cello.clustering.common import Infomap, Walktrap
    # weighted
    walktrap = Walktrap(weighted=True)
    walktrap.name = "Walktrap"
    infomap = Infomap(weighted=True) 
    infomap.name = "Infomap"

    DEFAULTS = [walktrap, infomap]

    if optionables == None : optionables = DEFAULTS
    
    view = EngineView(clustering_engine(optionables))
    view.set_input_type(EdgeList())
    view.add_output("clusters", export_clustering,  vertex_id_attr='uuid')

    api.register_view(view, url_prefix=prefix)
    return api


def explore_api(name, graphdb, engines):
    """ API over tmuse elastic search
    """
    api = ReliureAPI(name,expose_route=False)

    # starred 
    view = EngineView(engines.starred_engine(graphdb))
    view.set_input_type(ComplexQuery())
    view.add_output("request", ComplexQuery())
    view.add_output("graph", export_graph, id_attribute='uuid')

    api.register_view(view, url_prefix="starred")

    # prox search returns graph only
    view = EngineView(engines.explore_engine(graphdb))
    view.set_input_type(ComplexQuery())
    view.add_output("request", ComplexQuery())
    view.add_output("graph", export_graph, id_attribute='uuid')

    api.register_view(view, url_prefix="explore")

    # prox expand returns [(node,score), ...]
    view = EngineView(engines.expand_prox_engine(graphdb))
    view.set_input_type(NodeExpandQuery())
    view.add_output("scores", lambda x:x)

    api.register_view(view, url_prefix="expand_px")


    # additive search
    view = EngineView(engines.additive_nodes_engine(graphdb))
    view.set_input_type(AdditiveNodes())
    view.add_output("graph", export_graph, id_attribute='uuid'  )

    api.register_view(view, url_prefix="additive_nodes")

    
    api = layout_api(engines, api)
    api = clustering_api(engines, api)

    import random
    import json
    import pickle
    from flask import request, jsonify
    from flask import Response, make_response
    

    @api.route("/<string:gid>.json", methods=['GET'])
    @api.route("/starred/<string:gid>.json", methods=['GET'])
    def _json_dump(gid):
        dumps = lambda g : json.dumps( export_graph(g, id_attribute='uuid') )
        return stargraph_dump(gid, dumps, 'json')

    @api.route("/<string:gid>.pickle", methods=['GET'])
    @api.route("/starred/<string:gid>.pickle", methods=['GET'])
    def _pickle_dump(gid):
        return stargraph_dump(gid, pickle.dumps, 'pickle')

    def stargraph_dump(gid, dumps, content_type):
        """ returns igraph pickled/jsonified starred graph  """

        engine = engines.starred_engine(graphdb)
        
        meta = graphdb.get_graph_metadata(gid)
        graph = engine.play({'graph':gid})['graph']

        for k,v in meta.iteritems():
            graph[k] = v

        response = make_response(dumps(graph))
        response.headers['Content-Type'] = 'application/%s' % content_type
        response.headers['Content-Disposition'] = 'inline; filename=%s.%s' % (gid, content_type)
        return response
        

    @api.route("/<string:gid>/random")
    def random_node(gid):

        return jsonify({ 'gid': gid})

        # Debug views
    @api.route("/<string:gid>/extraction/<string:text>", methods=['GET'])
    @api.route("/<string:gid>/extraction", methods=['POST'])
    def _extract(gid, text=None):
        """
            POST /<string:graph>/extraction {
                gid: graph,
                uuids : [uuid, uuid]
            }
        """

        if request.method == "GET":
            labels = text.split(',')
            nodes = [ graphdb.get_node_by_name(gid, label) for label in labels ]
            p0_uuids = [ node['uuid'] for node in nodes ]
        elif request.method == "POST":
            assert graph == request.json.get('gid', None)
            p0_uuids = request.json.get('uuids')

        prox = graphdb.proxemie(gid, p0_uuids, limit=50, n_step=3)

        return jsonify({ 'gid': gid, 'nodes': p0_uuids , 'extraction':prox})






    return api
