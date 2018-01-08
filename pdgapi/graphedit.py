#-*- coding:utf-8 -*-

from flask import request, jsonify, current_app, url_for
from flask_login import login_required , current_user

import json
from reliure.web import ReliureAPI

from pdglib.graphdb_interface import GraphError, ApiError




def graphedit_api(name, app, graphdb, login_manager, socketio):
    """ graph  api """
    api = ReliureAPI(name,expose_route = False)

    infos = {
            "desc" : "graph api",
            "version" : "0.1dev",
            "name" : name,
            "db" : repr(graphdb)
        }


    def make_pad_url(name):
        return ""

    def broadcast(*args):
        if socketio: socketio.broadcast( *args )
 
    def broadcast_multi(messages):
        if socketio: socketio.broadcast_multi( messages )
 

    """ Graph """

    @api.route("/list", methods=['GET'])
    @api.route("/list/page/<int:page>", methods=['GET'])
    def http_list(page=1, order_by="name"):
        offset = 30
        data = graphdb.list_graphs(page, offset=offset, order_by=order_by, meta=False, reverse=False, root_page_url=url_for("%s.http_list" % api.name) )

        return jsonify( data )
        

    @api.route("/create", methods=['POST'])
    @api.route("/g/<string:gid>", methods=['POST'])
    @api.route("/g/<string:gid>", methods=['PUT'])
    @login_required
    def edit_graph(gid=None):
        """ create new graph  """
        username = current_user.username
        form = request.json

        if form is None:
            form = request.form

        keys = ['description' , 'tags', 'image']

        properties = { k: form.get(k, "") for k in keys }
               
        data = { 'graph': gid,
                 'username': username
               }

        if request.method == "POST":
            if gid == None : gid = form['name']
            
            g = graphdb.create_graph( username, gid, properties)
            properties['pad_url'] = make_pad_url(name)
            data['graph'] = gid
            data['status'] = 'created'
            broadcast( 0,'new graph', data )

        if request.method == "PUT" and gid is not None:
            graphdb.update_graph(username, gid, properties)
            data['status'] = 'edited'
            data['properties'] = properties
            broadcast( gid,'edit graph', data )
            
        return  jsonify(graphdb.get_graph(gid))
        

    @api.route("/g/<string:gid>", methods=['GET'])
    def get_graph_metadata(gid):
        """ get  graph metadata  """

        data = { gid: graphdb.get_graph_metadata(gid) }

        return jsonify(data)

    #@api.route("/g/<string:gid>/drop", methods=['GET'])
    @api.route("/g/<string:gid>", methods=['DELETE'])
    @login_required
    def delete_graph(gid):
        """ get  graph metadata  """
        
        username = current_user.username if current_user.is_authenticated else ""
        graph =  graphdb.get_graph(gid)

        if graph and app.config.get( "ALLOW_OWNER_DELETE_GRAPH" , False) and graph['meta']['owner'] == username:
            
            graphdb.destroy_graph(gid)
            
            data = { 'graph': gid,
                     'status' : 'deleted'
                   }

            return jsonify(data)

        else:
            return current_app.login_manager.unauthorized()



    """ Subgraph """
    @api.route("/g/<string:gid>/subgraph", methods=['POST'])
    def extract_subgraph(gid):
        """
        returns json subgraph in a list of triples. (src, props, target)
        input: json post request
                {
                    nodes : [ uuid, .. ]
                }

        output:
                {   graph : gid,
                    subgraph : [ ( uuid_source, {edge properties}, uuid_target ) ]
                }
        """

        uuids = request.json.get('nodes')
        subgraph = graphdb.get_subgraph(gid, uuids)

        data = {    "graph" : gid,
                    "subgraph": subgraph,
                }
        return jsonify(data)


    """ Completion """
    @api.route("/g/<string:gid>/complete/<string:obj_type>/<string:prefix>", methods=['GET'])
    @api.route("/g/<string:gid>/complete", methods=['POST'])
    def complete_label(gid, obj_type=None, prefix=None):

        start = 0

        if request.method == 'GET':
            start = request.args.get('start', start)


        if request.method == 'POST':
            obj_type = request.json.get('obj_type')
            prefix = request.json.get('prefix')
            start = request.json.get('start')

        start = int(start)
        complete = graphdb.complete_label(gid, obj_type, prefix, start, 100)
        data = {    "graph" : gid,
                    "obj_type"  : obj_type,
                    "prefix"  : prefix,
                    "complete": complete,
                    "start": start,
                    "count": len(complete),
               }

        return jsonify(data)


    """ Schema """

    @api.route("/g/<string:gid>/schema", methods=['GET','POST'])
    def get_schema(gid):
        """ Get graph schema """

        data = { 'graph': gid,
                 'schema' : {
                    "nodetypes" : graphdb.get_node_types(gid),
                    "edgetypes" : graphdb.get_edge_types(gid),
                 }
               }

        return jsonify(data)

    @api.route("/g/<string:gid>/schema", methods=['POST'])
    @login_required
    def set_schema(gid):
        """ Edit node data """
        data = { 'graph': gid,
                 'status' : 'changed'
               }

        raise GraphError('Set schema Not implemented')

        return jsonify( data )


    #  NodeTypes
    @api.route("/g/<string:gid>/nodetypes", methods=['GET'])
    def get_node_types(gid):
        return jsonify( { "graph": gid,
                          "nodetypes" : graphdb.get_node_types(gid),
                        }
                      )


    @api.route("/g/<string:gid>/nodetype/<string:uuid>", methods=['GET'])
    def get_nodetype(gid, uuid):
        #username = current_user.username

        nodetype = graphdb.get_node_type( gid, uuid ) 
        nodetype.update({ 'graph': gid  })
               
        return jsonify(nodetype)




    @api.route("/g/<string:gid>/nodetype", methods=['POST'])
    @api.route("/g/<string:gid>/nodetype/<string:uuid>", methods=['PUT'])
    @login_required
    def edit_nodetype(gid, uuid=None):
        """ Edit node data
        POST to create a new node type
        PUT to update existing node type !!! append properties only
        {
            name : <str> node type name ,
            desc : <str> node type description ,
            properties : {
                name : json serialized  cello type,
                name : ...
            },
            material: {}
        }
        """
        username = current_user.username

        data = request.json
        name = data.pop('name', "")
        description = data.pop('description', "")
        properties = data.pop('properties', {})

        resp = { 'graph': gid,
                 'username': username
               }
        # TODO check properties type
        if name == "" : raise ValueError("NodeType should have a name.")
        for k, v  in properties.iteritems():
            if k == "": raise ValueError("Properties should have a name.")

        # creation
        if request.method == "POST" and uuid is None:

            nodetype = graphdb.create_node_type( username, gid, name, properties, description)
            nodetype.update(
                    {
                     'graph': gid,
                     'status':'created',
                     'username' : username,
                   })
                   
            broadcast(uuid, 'new nodetype', nodetype)

            return jsonify( nodetype )

        # update
        elif request.method == "PUT" and uuid is not None :

            nodetype = graphdb.update_nodetype(uuid, properties, description)
            nodetype.update(
                    {
                     'graph': gid,
                     'status':'edited',
                     'username' : username,
                   })
            
            broadcast(uuid, 'edit nodetype', nodetype)

            return jsonify( nodetype )

        else:
            return 404


    """ Edge types """

    @api.route("/g/<string:gid>/edgetype/<string:uuid>", methods=['GET'])
    def get_edgetype(gid, uuid):
        #username = current_user.username

        resp = { 'graph': gid,
               }
        edgetype = graphdb.get_edge_type(uuid)

        return jsonify(edgetype)


    @api.route("/g/<string:gid>/edgetypes", methods=['GET'])
    def get_edgetypes(gid):
        edgetypes = graphdb.get_edge_types(gid)
        return jsonify( { "graph": gid,
                          "edgetypes" : edgetypes,
                        }
                      )


    @api.route("/g/<string:gid>/edgetype", methods=['POST'])
    @api.route("/g/<string:gid>/edgetype/<string:uuid>", methods=['POST', 'PUT'])
    @login_required
    def edit_edge_type(gid, uuid=None):
        """ Edit node data """
        username = current_user.username

        data = request.json
        name = data.pop('name', "")
        description = data.pop('description', "")
        properties = data.pop('properties', {})

        if name == "" : raise ValueError("EdgeType should have a name.")
        for k, v  in properties.iteritems():
            if k == "": raise ValueError("Properties should have a name.")


        # creation
        if  request.method == "POST" and  uuid is None :

            edgetype = graphdb.create_edge_type( username, gid, name, properties, description)
            edgetype.update(
                    {
                     'graph': gid,
                     'status':'edited',
                     'username' : username,
                   })
            broadcast(uuid, 'new edgetype', edgetype)
            
            return jsonify( edgetype )

        # update
        elif request.method == "PUT" and uuid is not None :

            #props = { x['name']: x['otype'] for x in properties }
            edgetype = graphdb.update_edgetype(uuid, properties, description)
            edgetype.update(
                    {
                     'graph': gid,
                     'status':'edited',
                     'username' : username,
                   })
                   
            broadcast(uuid, 'edit edgetype', edgetype)

            return jsonify( edgetype )

        else:
            return 404



    """ Node """

    @api.route("/g/<string:gid>/nodes", methods=['POST'])
    @login_required
    def create_nodes(gid):
        """ batch insert nodes """
        username = current_user.username
        
        #print request.args
        #print request.values
        #print request.data
        #print request.stream.read()
        #print request.get_json(force=True, silent=False)
                
        data = request.json
        
        nodes = data['nodes'] 
        res = []

        # validate nodes properties
        
        for node in nodes: pass

        uuids = graphdb.batch_create_nodes(username, gid, nodes )

        #assert len(uuids) == len(nodes)

        # post to Notifications Server
        messages = [ {
                    "username": username,
                    "action": "new node",
                    
                    "graph": gid, 
                    "uuid": uuid,
                    "properties" : nodes[i]['properties'],
                    
                    "status" : "created"
                    
                  } for i, uuid in uuids ]
                  
        broadcast_multi( messages )

        return jsonify( {
                          "action": "new node",
                          'graph':gid,
                          'username' : username,
                          'results': uuids } )



    @api.route("/g/<string:gid>/nodes/find", methods=['POST'])
    @api.route("/g/<string:gid>/nodes/find/<string:node_type>", methods=['GET'])
    def find_nodes(gid, node_type=None):
        """ Get node data
        
        """

        start=0; size=100; properties={}

        if request.method == "GET":
            start = int(request.args.get('start', start))
        if request.method == "POST":
            form = request.json
            start = form.get('start', 0)
            size  = min(form.get('size', 10), 100)
            node_type = form.get('nodetype')
            properties = form.get('properties')

        nodes = graphdb.find_nodes(gid, node_type, properties, start, size)

        data = { 'graph': gid,
                 'nodetype' : node_type, # uuid
                 'start' : start,
                 'size' : size,
                 'properties' : properties,
                 #'uuids' : []
                 'nodes' : nodes,
                 'count' : len(nodes)
               }

        return jsonify( data )

    @api.route("/g/<string:gid>/node/<string:uuid>", methods=['GET'])
    def get_node_by_id(gid, uuid):
        return _get_node(gid, uuid)

    @api.route("/g/<string:gid>/node/<string:uuid>/by_name", methods=['GET'])
    def get_node_by_name(gid, uuid):
        return _get_node(gid, uuid, by_name=True)

    def _get_node(gid, uuid, by_name=False):
        """ Get node data """

        # TODO check node is in graph
    
        if by_name:
            node = graphdb.get_node_by_name(gid, uuid)
        else :
            node = graphdb.get_node(gid, uuid)

        node.update( {
            'graph': gid,
            'label' if by_name else 'uuid' : uuid,
            'status' : 'read'
        })

        return jsonify( node )

    @api.route("/g/<string:gid>/node/<string:uuid>/neighbors", methods=['GET','POST'])
    def node_neigbhors( gid, uuid):
        """ Function doc
        :param gid: <str> graph
        :param uuid: <uuid> node uuid
        :returns : neighbors list starting from `start` with a size of `size`
        """
        SIZE= int(request.args.get('size', 100))
        
        if request.method =='GET':
            start = int(request.args.get('start', 0))
        elif  request.method =='POST':
            start = request.json.get('start', 0)

        neighbors = graphdb.get_graph_neighbors(gid, uuid, filter_edges=None, filter_nodes=None, filter_properties=None, mode='ALL', start=start, size=SIZE )

        data = {
                'graph' : gid,
                'node'  : uuid,
                'start' : start,
                'neighbors' : neighbors,
                'size' : SIZE,
                'length' : len(neighbors),
                'count' : graphdb.count_neighbors(gid, uuid, filter_edges=None, filter_nodes=None, filter_properties=None, mode='ALL' )
            }
        return jsonify( data )


    @api.route("/g/<string:gid>/node/<string:uuid>/neighbors/count", methods=['GET','POST'])
    def count_node_neigbhors(gid, uuid):
        """ Function doc
        :param gid: <str> graph
        :param uuid: <uuid> node uuid
        :returns : neighbors count
        """
        if request.method =='GET':
            pass
        elif  request.method =='POST':
            pass

        # TODO parse args for filter

        edges = graphdb.count_neighbors(uuid, filter_edges=None, filter_nodes=None, filter_properties=None, mode='ALL' )

        data = {
                'graph' : gid,
                'node'  : uuid,
                'neighbors': edges
            }
        return jsonify( data )

    @api.route("/g/<string:gid>/node", methods=['POST'])
    @api.route("/g/<string:gid>/node/<string:uuid>", methods=[ 'PUT'])
    @login_required
    def edit_node(gid, uuid=None):
        """ Edit node data """
        data = request.json

        if request.method == "POST":
            if uuid is not None:
                raise ApiError('POST method is not allowed with a uuid, use PUT to edit ');

        if request.method == "PUT":
            if uuid is None:
                raise ApiError('PUT method expect a uuid, use POST to create a node ');

        resp = post_node(current_user.username, gid, uuid, data)

        return jsonify( resp )

    def post_node(username, gid, uuid, data):

        # ::: TODO :::
        # check node uuid is in graph
        # check node_type
        # check properties key & values
        # check update/create node


        resp = {
                 'graph': gid,
                 'uuid': uuid,
                 'username' : current_user.username,
               }
        # creation

        nt_uuid = data.pop('nodetype')
        props = data.pop('properties', {})
        label = props.get('label', "")
        
        nodetype = graphdb.get_node_type( gid, nt_uuid )

        if nodetype is None:
            raise ApiError("Nodetype '%s' is unknown" % nt_uuid)

        # TODO extract label pattern like %name
        

        if uuid is None and request.method == "POST" :

            uuid = graphdb.create_node(username, gid, nt_uuid, props)
            resp['uuid'] = uuid
            resp['status'] = "created"
            resp['label'] = label

            broadcast( gid, "new node", resp)
            return resp

        # edition
        elif uuid and request.method == "PUT" :
            # TODO:: check that node belongs to this graph
            graphdb.change_node_properties(username, uuid, props)

            resp['status'] = "edited"
            resp['label'] = label
            
            broadcast(uuid, "edit node", resp)
            return resp
        # error
        else:
            return 404

    @api.route("/g/<string:gid>/nodes", methods=['PUT'])
    @login_required
    def edit_nodes(gid):

        return 500, "unimplemented"


    @api.route("/g/<string:gid>/node/<string:uuid>", methods=['DELETE'])
    @login_required
    def delete_node(gid, uuid):
        """ Delete
         """
        node = graphdb.get_node(gid, uuid)

        deleted = graphdb.delete_node(current_user.username, gid, uuid)

        data = {
                 'graph': gid,
                 'uuid': uuid,  
                 'username': current_user.username,
                 'label': node['properties']['label'],
                 'status': "deleted",
               }

        broadcast(uuid, 'delete node', data)

        return jsonify( data )


    # ~~~ Stars ~~~
    
    def _set_nodes_starred(gid, nodes, starred):

        graphdb.set_nodes_starred(gid, nodes, starred)

        data = { 'graph': gid,
                 'nodes' : nodes,
                 'count' : len(nodes),
                 'star' : starred
               }
        return data
        
    @login_required
    @api.route("/g/<string:gid>/nodes/star", methods=['POST'])
    def star_nodes(gid):
        nodes = request.json.get('nodes', [])
        return jsonify( _set_nodes_starred(gid, nodes, True))
        
    @login_required
    @api.route("/g/<string:gid>/nodes/unstar", methods=['POST'])
    def unstar_nodes(gid):
        nodes = request.json.get('nodes', [])
        return jsonify( _set_nodes_starred(gid, nodes, False))

    @api.route("/g/<string:gid>/node/<string:uuid>/star", methods=['GET','POST'])
    @login_required
    def star_node(gid, uuid):
        return jsonify( _set_nodes_starred(gid, [uuid], True))

    @api.route("/g/<string:gid>/node/<string:uuid>/unstar", methods=['GET','POST'])
    @login_required
    def unstar_node(gid, uuid):
        return jsonify( _set_nodes_starred(gid, [uuid], False))
        

    @api.route("/g/<string:gid>/upvote", methods=['GET'])
    @login_required
    def user_upvote_graph(gid):
        
        username = current_user.username if current_user.is_authenticated else ""
        return jsonify( graphdb.toggle_user_updownvote_graph( username, gid, 'up' ))


    @api.route("/g/<string:gid>/downvote", methods=['GET'])
    @login_required
    def user_downvote_graph(gid):
        
        username = current_user.username if current_user.is_authenticated else ""
        return jsonify(
            graphdb.toggle_user_updownvote_graph( username, gid , 'down')
        )
        
    @api.route("/g/<string:gid>/vote", methods=['GET'])
    @login_required
    def get_user_graph_vote(gid):
        
        username = current_user.username if current_user.is_authenticated else ""
        return jsonify( graphdb.get_user_updownvote_graph( username, gid) )



    """ Edges """



    @api.route("/g/<string:gid>/edge/<string:uuid>", methods=['GET'])
    def get_edge(gid, uuid):
        """ Get edge data """

        # TODO check edge is in graph

        edge = graphdb.get_edge(uuid)
        
        edge.update(
               {
                 'graph': gid,
               })

        return jsonify( edge )

    @api.route("/g/<string:gid>/edges", methods=['POST'])
    @login_required
    def edit_edges(gid):

        messages = []
        data = request.json
        
        edges = data['edges']
        uuids = graphdb.batch_create_edges(current_user.username, gid, edges )

        for i, uuid in uuids:

            edge = edges[i]
            edge['uuid'] = uuid
            
            edge.update({
                "graph": gid, 
                "username":current_user.username,
                "status" : "created",                
            })
                   
            edge.update({
                "action": "new edge",
            })
            messages.append(dict(edge))
            
            edge.update({
                "action": "new edge from",
            })
            messages.append(dict(edge))

            edge.update({
                "action": "new edge to",
            })
            messages.append(dict(edge))
            
        broadcast_multi(messages)
        
        return jsonify( { 'graph':gid,
                          'username' : current_user.username,
                          'status': 'created',
                          'results': uuids } )

    @api.route("/g/<string:gid>/edges/find", methods=['POST'])
    def find_edges(gid):
        """ Get node data """
        form = request.json

        start = form.get('start', 0)
        size = form.get('size', 100)
        edge_type = form.get('edge_type')
        properties = form.get('properties')

        edges = graphdb.find_edges(gid, edge_type, properties, start, size)

        data = { 'graph': gid,
                 'edge_type' : edge_type,
                 'start' : start,
                 'size' : size,
                 'properties' : properties,
                 'edges' : edges
               }

        return jsonify( data )


    @api.route("/g/<string:gid>/edge", methods=['POST'])
    @api.route("/g/<string:gid>/edge/<string:uuid>", methods=['PUT'])
    @login_required
    def edit_edge(gid, uuid=None):
        """ Edit edge data
        One can update properties for edges not source or target
        """
        username = current_user.username
        data = request.json
        edge = {}

        edgetype = data.pop('edgetype')
        props  =  data.pop('properties', {})
        #label  = props.pop('label', "")
        
        # ::: TODO :::
        # check edge_type
        # check properties key & values
        # check update/create edge

        # creation
        if uuid is None and request.method == "POST" :
            # TODO has any ?
            source = data.pop('source')
            target = data.pop('target')

            assert source and target, "Wrong source or target for an edge (%s,%s) " % (source, target)

            uuid = graphdb.create_edge(username, gid, edgetype, props, source, target)
            
            edge = graphdb.get_edge(uuid)

            edge.update( {                    
                     'graph': gid,
                     'username': username,
                     'status': 'created',
                  })
            
            broadcast(uuid, 'new edge', edge)

        elif uuid and request.method == "PUT":
            # edition
            graphdb.change_edge_properties(username, uuid, props)
            
            edge = graphdb.get_edge(uuid)

            edge.update( {                    
                     'graph': gid,
                     'username': username,
                     'status': 'edited',
                  })
                  
            broadcast(uuid, 'edit edge', edge)
            
        else:
            return 404


        return jsonify( edge )

    @api.route("/g/<string:gid>/edge/<string:uuid>", methods=['DELETE'])
    @login_required
    def delete_edge(gid, uuid):
        """ Delete edge """

        # TODO : mark edge deleted
        graphdb.delete_edge(current_user.username, gid, uuid)

        data = {
                 'graph': gid,

                 'uuid': uuid,  
                 'properties': {},

                 'username': current_user.username,
                 'status': "deleted",
               }

        broadcast(uuid, 'delete edge', data )

        return jsonify( data )


    return api


