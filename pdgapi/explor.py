#-*- coding:utf-8 -*-

from reliure.web import ReliureAPI, EngineView
from reliure.pipeline import Optionable, Composable
from reliure.types import GenericType
from reliure.engine import Engine

from cello.clustering import export_clustering

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
        expand = data.get('expand', None)
        nodes_uuid = data.get('nodes', [])
        weights = data.get('weights', [])

        if gid is None :
            raise ValueError('graph should not be null')
        if expand is None :
            raise ValueError('`expand` should not be null')

        if len(weights) and len(weights) != len(expand):
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
    from cello.layout.simple import DrlLayout

    LAYOUTS = [

        ("2D_Force_directed" , FruchtermanReingoldLayout(dim=2, weighted=True) ),
        ("3D_Force_directed" , FruchtermanReingoldLayout(dim=3, weighted=True) ),

        ("2D_KamadaKawai" , KamadaKawaiLayout(dim=2) ),
        ("3D_KamadaKawai" , KamadaKawaiLayout(dim=3) ),
        
        ("3DMds"         , ProxLayoutMDS(dim=3) | Shaker(kelastic=.9) ),
        ("2DMds"         , ProxLayoutMDS(dim=2 ) | Shaker(kelastic=.9) ),
        
        ("3DPca"         , ProxLayoutPCA(dim=3, ) | Shaker(kelastic=.9) ),
        ("3DPcaWeighted" , ProxLayoutPCA(dim=3, weighted=True) | Shaker(kelastic=.9) ),
        ("2DRandomProj"  , ProxLayoutRandomProj(dim=2) ),
        #("3DRandomProj"  , ProxLayoutRandomProj(dim=3) ),
        ("3DOrdered"     , ProxMDSSugiyamaLayout(dim=3) | Shaker(kelastic=0.9) ),
        # 2D
        ("2DPca"         , ProxLayoutPCA(dim=2) | Shaker(kelastic=1.8) ),
        # tree
        ("DrlLayout" , DrlLayout(dim=2) | Shaker(kelastic=0.8) ),
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
        engine = Engine("gbuilder", "clustering", "labelling")
        engine.gbuilder.setup(in_name="request", out_name="graph", hidden=True)
        engine.clustering.setup(in_name="graph", out_name="clusters")
        engine.labelling.setup(in_name="clusters", out_name="clusters", hidden=True)

        engine.gbuilder.set(engines.edge_subgraph) 
        engine.clustering.set(*optionables)

        ## Labelling
        from cello.clustering.labelling.model import Label
        from cello.clustering.labelling.basic import VertexAsLabel, TypeFalseLabel, normalize_score_max

        def _labelling(graph, cluster, vtx):
            return  Label(vtx["uuid"], score=1, role="default")
        
        labelling = VertexAsLabel( _labelling ) | normalize_score_max
        engine.labelling.set(labelling)

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
    api = ReliureAPI(name,expose_route=True)

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
