import gurobipy as gp
from gurobipy import GRB
import time
import networkx as nx

def StRAM(graph, start_node, phi, output = 0):

    graph = graph.to_directed()

    edges = set(graph.edges)
    nodes = set(graph.nodes)
    distance = nx.get_edge_attributes(graph, "distance")
    pcg = nx.get_node_attributes(graph, "pcg")

    ############### PRE MODELO

    m = gp.Model('MST')
    m.setParam('OutputFlag', output)

    x = m.addVars(edges, vtype=GRB.BINARY, name='x')
    y = m.addVars(nodes, vtype=GRB.BINARY, name='y')
    f = m.addVars(edges, vtype=GRB.CONTINUOUS, name='f')

    m.setObjective(gp.quicksum(
        x[i,j]*distance[i,j] for i,j in edges    
    ), GRB.MAXIMIZE)

    m.addConstr(gp.quicksum(x[i,j] for i,j in edges) == len(nodes) - 1)

    m.addConstr(gp.quicksum(f[start_node,j] for j in nodes if (start_node,j) in edges) == len(nodes) - 1)

    m.addConstrs(gp.quicksum( f[i,j] for i,_j in edges if _j == j ) -
                    gp.quicksum( f[j,k] for _j,k in edges if _j == j ) 
                        == 1 for j in nodes if j != start_node)

    m.addConstrs(f[i,j] <= (len(nodes) - 1) * x[i,j] for (i,j) in edges if j != start_node)

    m.addConstrs(gp.quicksum(x[i,j] for i,_j in edges if _j == j ) == y[j] for j in nodes if j != start_node)

    m.addConstr(y[start_node] == 1)

    #m.addConstr(gp.quicksum(x[i,j] for i,j in edges) == len(nodes) - 1)

    m.optimize()

    if m.status == GRB.INFEASIBLE:
        m.computeIIS()
        m.write("model.ilp")
        raise Exception("El pre-modelo es infactible")    

    _x = m.getAttr('x', x)
    _y = m.getAttr('x', y)

    w1 = 1/(sum(pcg[j] * _y[j] for j in nodes) - pcg[start_node])
    w2 = 1/(sum(distance[i,j] * _x[i,j] for i,j in edges))
    w3 = sum(pcg[j] * _y[j] for j in nodes) 

    #print(f'W1: {w1}')
    #print(f'W2: {w2}')
    #print(f'W3: {w3}')

    ############### PRE MODELO

    m = gp.Model('STN')
    m.setParam('OutputFlag', output)

    x = m.addVars(edges, vtype=GRB.BINARY, name='x')
    y = m.addVars(nodes, vtype=GRB.BINARY, name='y')
    f = m.addVars(edges, vtype=GRB.CONTINUOUS, name='f')

    m.setObjective(
        w1 * gp.quicksum(y[j]*pcg[j] for j in nodes) -
        w2 * gp.quicksum(x[i,j]*distance[i,j] for i,j in edges)
    , GRB.MAXIMIZE)
    
    m.addConstrs(gp.quicksum(x[i,j] for i,_j in edges if _j == j ) == y[j] for j in nodes if j != start_node)
    
    m.addConstrs(gp.quicksum( f[i,j] for i,_j in edges if _j == j  ) -
                    gp.quicksum( f[j,k] for _j,k in edges if _j == j ) 
                        == y[j] for j in nodes if j != start_node)
    
    m.addConstrs(f[i,j] <= (len(nodes) - 1) * x[i,j] for (i,j) in edges if j != start_node)
    
    m.addConstr(gp.quicksum(pcg[j] * y[j] for j in nodes if j != start_node) <= w3 * phi)
    
    # m.addConstr(gp.quicksum(y[j] for j in nodes) == k_max)
    
    m.addConstr(gp.quicksum(x[start_node,j] for j in nodes if (start_node,j) in edges) >= 1)

    m.addConstr(y[start_node]== 1)

    m.optimize()

    if m.status == GRB.INFEASIBLE:
        m.computeIIS()
        m.write("model.ilp")
        raise Exception("El modelo es infactible")    
    
    return (m,x,y)



def RGEN(graph, start_nodes, phi, output = 0):

    graph = graph.to_directed()
    ############### PRE MODELO

    edges = list(set(graph.edges))
    nodes = list(set(graph.nodes))
    distance = nx.get_edge_attributes(graph, "distance")
    pcg = nx.get_node_attributes(graph, "pcg")

    m1 = gp.Model('MST')
    m1.setParam('OutputFlag', 0)

    x = m1.addVars(edges, vtype=GRB.BINARY, name='x')
    y = m1.addVars(nodes, vtype=GRB.BINARY, name='y')
    f = m1.addVars(edges, vtype=GRB.CONTINUOUS, name='f')

    m1.setObjective(gp.quicksum(
        x[i,j]*distance[i,j] for i,j in edges 
    ), GRB.MAXIMIZE)

    m1.addConstr(gp.quicksum(x[i,j] for i,j in edges) == len(nodes) - 1)
    
    m1.addConstr(gp.quicksum(f[start_nodes[0],j] for j in nodes if (start_nodes[0],j) in edges) == len(nodes) - 1)

    m1.addConstrs(gp.quicksum( f[i,j] for i,_j in edges if _j == j ) -
                    gp.quicksum( f[j,k] for _j,k in edges if _j == j ) 
                        == 1 for j in nodes if j != start_nodes[0])

    m1.addConstrs(f[i,j] <= (len(nodes) - 1) * x[i,j] for (i,j) in edges if j != start_nodes[0])

    m1.addConstrs(gp.quicksum(x[i,j] for i,_j in edges if _j == j ) == y[j] for j in nodes if j != start_nodes[0])

    m1.addConstrs(y[i] == 1 for i in start_nodes)

    m1.optimize()

    if m1.status == GRB.INFEASIBLE:
        m1.computeIIS()
        m1.write("model.ilp")  
        raise Exception("El pre-modelo es infactible")


    _x = m1.getAttr('x', x)
    _y = m1.getAttr('x', y)

    w1 = 1/(sum(pcg[j] * _y[j] for j in nodes) - pcg[start_nodes[0]])
    w2 = 1/(sum(distance[i,j] * _x[i,j] for i,j in edges))
    w3 = sum(pcg[j] * _y[j] for j in nodes) 

    #print(f'W1: {w1}')
    #print(f'W2: {w2}')
    #print(f'W3: {w3}')


    ############### MODELO

    m = gp.Model('RGEN')   

    m.setParam('OutputFlag', output) 

    x = m.addVars(edges, vtype=GRB.BINARY, name='x')
    y = m.addVars(nodes, vtype=GRB.BINARY, name='y')
    f = m.addVars(edges, vtype=GRB.CONTINUOUS, name='f')
    p = m.addVar(vtype=GRB.CONTINUOUS, name='p')

    m.setObjective(
        w1 * gp.quicksum(y[j]*pcg[j] for j in nodes) -
        w2 * gp.quicksum(x[i,j]*distance[i,j] for i,j in edges) -
        1000 * p
    , GRB.MAXIMIZE)
    
    m.addConstrs(gp.quicksum(x[i,j] for i,_j in edges if _j == j ) == y[j] for j in nodes if j != start_nodes[0])
    
    m.addConstrs(gp.quicksum( f[i,j] for i,_j in edges if _j == j  ) -
                    gp.quicksum( f[j,k] for _j,k in edges if _j == j ) 
                        == y[j] for j in nodes if j != start_nodes[0])
    
    m.addConstrs(f[i,j] <= (len(nodes) - 1) * x[i,j] for (i,j) in edges if j != start_nodes[0])

    m.addConstr(gp.quicksum(pcg[j] * y[j] for j in nodes if j != start_nodes[0]) <= w3 * (phi+p))
    
    m.addConstr(gp.quicksum(x[start_nodes[0],j] for j in nodes if (start_nodes[0],j) in edges) >= 1)
        
    m.addConstrs(y[i]== 1 for i in start_nodes)   
    
    m.addConstr(p >= 0)

    m.optimize()

    if m.status == GRB.INFEASIBLE:
        m.computeIIS()
        m.write("model.ilp") 
        raise Exception("El modelo RGEN es infactible")    
    
    return (m,x,y,p)


def RGENF(graph, start_nodes, phi, output = 0):

    graph = graph.to_directed()
    edges = list(set(graph.edges))
    nodes = list(set(graph.nodes))
    distance = nx.get_edge_attributes(graph, "distance")
    pcg = nx.get_node_attributes(graph, "pcg")

    ############### PRE MODELO
    m1 = gp.Model('MST')
    m1.setParam('OutputFlag', 0)

    x = m1.addVars(edges, vtype=GRB.BINARY, name='x')
    y = m1.addVars(nodes, vtype=GRB.BINARY, name='y')
    f = m1.addVars(edges, vtype=GRB.CONTINUOUS, name='f')

    # Obj. F.
    m1.setObjective(gp.quicksum(
        x[i,j]*distance[i,j] for i,j in edges 
    ), GRB.MAXIMIZE)

    # edgeA
    m1.addConstr(gp.quicksum(x[i,j] for i,j in edges) <= len(nodes) - 1)
    # flujo2A
    m1.addConstr(gp.quicksum(f[start_nodes[0],j] for j in nodes if (start_nodes[0],j) in edges) <= len(nodes) - 1)
    # flujoA
    m1.addConstrs(gp.quicksum( f[i,j] for i,_j in edges if _j == j ) -
                    gp.quicksum( f[j,k] for _j,k in edges if _j == j ) 
                        == y[j] for j in nodes if j != start_nodes[0])
    # cicloA
    m1.addConstrs(f[i,j] <= (len(nodes) - 1) * x[i,j] for (i,j) in edges if j != start_nodes[0])
    # activaciónA
    m1.addConstrs(gp.quicksum(x[i,j] for i,_j in edges if _j == j ) == y[j] for j in nodes if j != start_nodes[0])
    #nodo_sA
    m1.addConstr(y[start_nodes[0]] == 1)
    # no_sale_destino
    m1.addConstrs(gp.quicksum(x[j,i] for _j,i in edges if _j==j) == 0 for j in start_nodes if j != start_nodes[0] )
    m1.optimize()

    if m1.status == GRB.INFEASIBLE:
        m1.computeIIS()
        m1.write("model.ilp")  
        raise Exception("El pre-modelo es infactible")
    
    _x = m1.getAttr('x', x)
    _y = m1.getAttr('x', y)

    w1 = 1/(sum(pcg[j] * _y[j] for j in nodes) - pcg[start_nodes[0]])
    w2 = 1/(sum(distance[i,j] * _x[i,j] for i,j in edges))
    w3 = sum(pcg[j] * _y[j] for j in nodes) 


    ############### MODELO
    m = gp.Model('RGEN')   

    m.setParam('OutputFlag', output) 

    x = m.addVars(edges, vtype=GRB.BINARY, name='x')
    y = m.addVars(nodes, vtype=GRB.BINARY, name='y')
    f = m.addVars(edges, vtype=GRB.CONTINUOUS, name='f')
    p = m.addVar(vtype=GRB.CONTINUOUS, name='p')

    m.setObjective(
        w1 * gp.quicksum(y[j]*pcg[j] for j in nodes) -
        w2 * gp.quicksum(x[i,j]*distance[i,j] for i,j in edges) -
        1000 * p
    , GRB.MAXIMIZE)

    # activacion
    m.addConstrs(gp.quicksum(x[i,j] for i,_j in edges if _j == j ) == y[j] for j in nodes if j != start_nodes[0])
    # flujo
    m.addConstrs(gp.quicksum( f[i,j] for i,_j in edges if _j == j  ) -
                    gp.quicksum( f[j,k] for _j,k in edges if _j == j ) 
                        == y[j] for j in nodes if j != start_nodes[0])
    # ciclo
    m.addConstrs(f[i,j] <= (len(nodes) - 1) * x[i,j] for (i,j) in edges if j != start_nodes[0])
    # pmiembros
    m.addConstr(gp.quicksum(pcg[j] * y[j] for j in nodes if j != start_nodes[0]) <= w3 * (phi+p))

    #m.addConstr(gp.quicksum(y[j] for j in nodes) == k_max)

    # inicio
    m.addConstr(gp.quicksum(x[start_nodes[0],j] for j in nodes if (start_nodes[0],j) in edges) >= 1)
    # presencia nodos conocidos
    m.addConstr(y[start_nodes[0]] == 1)
    #holgura phi
    m.addConstr(p >= 0)
    # nodos finales
    m.addConstrs(gp.quicksum(x[i,j] for i,_j in edges if _j == j) == 1 for j in start_nodes if j != start_nodes[0])
    # no sale destino
    m.addConstrs(gp.quicksum(x[j,i] for _j,i in edges if _j == j) == 0 for j in start_nodes if j != start_nodes[0])

    m.optimize()

    if m.status == GRB.INFEASIBLE:
        m.computeIIS()
        m.write("model.ilp") 
        raise Exception("El modelo RGEN-F es infactible")    
    
    return (m,x,y,p)

