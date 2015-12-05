
from collections import namedtuple

import numpy as np
import cvxpy as cp
from numpy.random import randn, rand

from epsilon.prox import eval_prox
from epsilon.expression_pb2 import ProxFunction

RANDOM_PROX_TRIALS = 10

import logging
logging.basicConfig(level=logging.DEBUG)

# Common variable
n = 10
x = cp.Variable(n)
p = cp.Variable(3)
X = cp.Variable(3,3)
t = cp.Variable(1)
p1 = cp.Variable(1)
q1 = cp.Variable(1)

class Prox(namedtuple(
        "Prox", ["prox_type", "objective", "constraint", "epigraph"])):
    def __new__(cls, prox_type, objective, constraint=None, epigraph=False):
        return super(Prox, cls).__new__(
            cls, prox_type, objective, constraint, epigraph)

def f_quantile():
    alpha = rand()
    return cp.sum_entries(cp.max_elemwise(alpha*x,(alpha-1)*x))

def f_dead_zone():
    eps = np.abs(randn())
    return cp.sum_entries(cp.max_elemwise(cp.abs(x)-eps, 0))

def f_hinge():
    return cp.sum_entries(cp.max_elemwise(x,0))

def f_least_squares(m):
    A = np.random.randn(m, n)
    b = np.random.randn(m)
    return cp.sum_squares(A*x - b)

def f_least_squares_matrix():
    m = 20
    k = 3
    A = np.random.randn(m, n)
    B = np.random.randn(m, k)
    X = cp.Variable(n, k)
    return cp.sum_squares(A*X  - B)

def C_linear_equality():
    m = 5
    A = np.random.randn(m, n)
    b = A.dot(np.random.randn(n))
    return [A*x == b]

def C_linear_equality_matrix_lhs():
    m = 5
    k = 3
    A = np.random.randn(m, n)
    X = cp.Variable(n, k)
    B = A.dot(np.random.randn(n, k))
    return [A*X == B]

def C_linear_equality_matrix_rhs():
    m = 3
    k = 5
    A = np.random.randn(k, m)
    X = cp.Variable(n, k)
    B = np.random.randn(n, k).dot(A)
    return [X*A == B]

def C_linear_equality_graph(m):
    A = np.random.randn(m, n)
    y = cp.Variable(m)
    return [y == A*x]

def C_linear_equality_graph_lhs(m, n):
    k = 3
    A = np.random.randn(m, n)
    B = A.dot(np.random.randn(n,k))
    X = cp.Variable(n, k)
    Y = cp.Variable(m, k)
    return [Y == A*X + B]

def C_linear_equality_graph_rhs(m, n):
    k = 3
    A = np.random.randn(m, n)
    B = np.random.randn(k, m).dot(A)
    X = cp.Variable(k, m)
    Y = cp.Variable(k, n)
    return [Y == X*A + B]

def C_linear_equality_multivariate():
    m = 5
    A = np.random.randn(m, n)
    b = np.random.randn(m)
    alpha = np.random.randn()
    y = cp.Variable(m)
    z = cp.Variable(m)
    return [z - (y - alpha*(A*x - b)) == 0]

def C_linear_equality_multivariate2():
    m = 5
    A = np.random.randn(m, n)
    y = cp.Variable(m)
    z = cp.Variable(m)
    return [z - (y - (1 - A*x)) == 0]

def C_non_negative_scaled():
    alpha = np.random.randn()
    return [alpha*x >= 0]

def C_soc_scaled():
    return [cp.norm2(randn()*x) <= randn()*t]

def C_soc_translated():
    return [cp.norm2(x + randn()) <= t + randn()]

def C_soc_scaled_translated():
    return [cp.norm2(randn()*x + randn()) <= randn()*t + randn()]

# Proximal operators
PROX_TESTS = [
    # Prox("SECOND_ORDER_CONE", None, C_soc_scaled),
    # Prox("SECOND_ORDER_CONE", None, C_soc_scaled_translated),
    # Prox("SECOND_ORDER_CONE", None, C_soc_translated),
    # Prox("SECOND_ORDER_CONE", None, lambda: [cp.norm2(x) <= t]),
    #Prox("MATRIX_FRAC", lambda: cp.matrix_frac(p, X)),
    #Prox("SIGMA_MAX", lambda: cp.sigma_max(X)),
    #Prox("SUM_KL_DIV", lambda: cp.kl_div(p1, q1)),
    Prox("AFFINE", lambda: randn(n).T*x),
    Prox("CONSTANT", lambda: 0),
    Prox("LAMBDA_MAX", lambda: cp.lambda_max(X)),
    Prox("MAX", lambda: cp.max_entries(x)),
    Prox("NEG_LOG_DET", lambda: -cp.log_det(X)),
    Prox("NEG_LOG_DET", lambda: -cp.log_det(X)),
    Prox("NON_NEGATIVE", None, C_non_negative_scaled),
    Prox("NON_NEGATIVE", None, lambda: [x >= 0]),
    Prox("NORM_1", lambda: cp.norm1(x)),
    Prox("NORM_2", lambda: cp.norm(X, "fro")),
    Prox("NORM_2", lambda: cp.norm2(x)),
    Prox("NORM_NUCLEAR", lambda: cp.norm(X, "nuc")),
    Prox("SEMIDEFINITE", None, lambda: [X >> 0]),
    Prox("SUM_DEADZONE", f_dead_zone),
    Prox("SUM_EXP", lambda: cp.sum_entries(cp.exp(x))),
    Prox("SUM_HINGE", f_hinge),
    Prox("SUM_HINGE", lambda: cp.sum_entries(cp.max_elemwise(1-x, 0))),
    Prox("SUM_HINGE", lambda: cp.sum_entries(cp.max_elemwise(1-x, 0))),
    Prox("SUM_INV_POS", lambda: cp.sum_entries(cp.inv_pos(x))),
    Prox("SUM_LARGEST", lambda: cp.sum_largest(x, 4)),
    Prox("SUM_LOGISTIC", lambda: cp.sum_entries(cp.logistic(x))),
    Prox("SUM_NEG_ENTR", lambda: -cp.sum_entries(cp.entr(x))),
    Prox("SUM_NEG_LOG", lambda: -cp.sum_entries(cp.log(x))),
    Prox("SUM_QUANTILE", f_quantile),
    Prox("SUM_SQUARE", f_least_squares_matrix),
    Prox("SUM_SQUARE", lambda: f_least_squares(20)),
    Prox("SUM_SQUARE", lambda: f_least_squares(5)),
    Prox("TOTAL_VARIATION_1D", lambda: cp.tv(x)),
    Prox("ZERO", None, C_linear_equality),
    Prox("ZERO", None, C_linear_equality_matrix_lhs),
    Prox("ZERO", None, C_linear_equality_matrix_rhs),
    Prox("ZERO", None, C_linear_equality_multivariate),
    Prox("ZERO", None, C_linear_equality_multivariate2),
    Prox("ZERO", None, lambda: C_linear_equality_graph(20)),
    Prox("ZERO", None, lambda: C_linear_equality_graph(5)),
    Prox("ZERO", None, lambda: C_linear_equality_graph_lhs(10, 5)),
    Prox("ZERO", None, lambda: C_linear_equality_graph_lhs(5, 10)),
    Prox("ZERO", None, lambda: C_linear_equality_graph_rhs(10, 5)),
    Prox("ZERO", None, lambda: C_linear_equality_graph_rhs(5, 10)),
]

# Epigraph operators
# PROX_TESTS += [
#     Prox("SUM_DEADZONE", None, lambda: [f_dead_zone() <= t], True),
#     Prox("HingeEpigraph", None, lambda: [f_hinge() <= t]),
#     Prox("InvPosEpigraph", None, lambda: [cp.sum_entries(cp.inv_pos(x)) <= t]),
#     Prox("KLDivEpigraph", None, lambda: [cp.kl_div(p1,q1) <= t]),
#     Prox("LambdaMaxEpigraph", None, lambda: [cp.lambda_max(X) <= t]),
#     Prox("LogisticEpigraph", None, lambda: [cp.sum_entries(cp.logistic(x)) <= t]),
#     Prox("MaxEntriesEpigraph", None, lambda: [cp.max_entries(x) <= t]),
#     Prox("NegativeEntropyEpigraph", None, lambda: [-cp.sum_entries(cp.entr(x)) <= t]),
#     Prox("NegativeLogDetEpigraph", None, lambda: [-cp.log_det(X) <= t]),
#     Prox("NegativeLogEpigraph", None, lambda: [-cp.sum_entries(cp.log(x)) <= t]),
#     Prox("NormFrobeniusEpigraph", None, lambda: [cp.norm(X, "fro") <= t]),
#     Prox("NormL1AsymmetricEpigraph", None, lambda: [f_norm_l1_asymmetric() <= t]),
#     Prox("NormL1Epigraph", None, lambda: [cp.norm1(x) <= t]),
#     Prox("NormNuclearEpigraph", None, lambda: [cp.norm(X, "nuc") <= t]),
#     Prox("SumExpEpigraph", None, lambda: [cp.sum_entries(cp.exp(x)) <= t]),
# ]

def run_prox(prox_function_type, prob, v_map, lam=1):
    eval_prox(prox_function_type, prob, v_map, lam)
    actual = {x: x.value for x in prob.variables()}

    # Compare to solution with cvxpy
    prob.objective.args[0] *= lam
    prob.objective.args[0] += sum(
        0.5*cp.sum_squares(x - v_map[x]) for x, v in v_map.iteritems())
    try:
        prob.solve()
    except cp.SolverError as e:
        # If CVXPY fails with default, try again with SCS
        prob.solve(solver=cp.SCS)

    try:
        for x in prob.variables():
            np.testing.assert_allclose(x.value, actual[x], rtol=1e-2, atol=1e-2)
    except AssertionError as e:
        # print objective value and constraints
        print
        print 'cvx:'
        print map(lambda x: x.value, prob.variables())
        print 'actual:'
        print actual.values()
        print 'vmap:'
        print v_map.values()
        print 'cvx obj:', prob.objective.value
        for c in prob.constraints:
            print c, c.value, map(lambda x: x.value, c.args)

        for x,v in actual.items():
            x.value = v
            print 'our obj:', prob.objective.value
        for c in prob.constraints:
            print c, c.value, map(lambda x: x.value, c.args)
        print

        raise e

def run_random_prox(prox, trial):
    np.random.seed(trial)
    v = np.random.randn(n)
    lam = np.abs(np.random.randn())
    lam = 1

    f = 0 if not prox.objective else prox.objective()
    C = [] if not prox.constraint else prox.constraint()

    # Form problem and solve with proximal operator implementation
    prob = cp.Problem(cp.Minimize(f), C)
    v_map = {x: np.random.randn(*x.size) for x in prob.variables()}

    run_prox(ProxFunction.Type.Value(prox.prox_type), prob, v_map, lam)

def test_random_prox():
    for prox in PROX_TESTS:
        for trial in xrange(RANDOM_PROX_TRIALS):
            yield run_random_prox, prox, trial

def test_second_order_cone():
    v_maps = [
        {x: np.zeros(10), t: np.array([0])},
        {x: np.arange(10), t: np.array([100])},
        {x: np.arange(10), t: np.array([10])},
        {x: np.arange(10), t: np.array([-100])},
        {x: np.arange(10), t: np.array([-10])}]

    for v_map in v_maps:
        prob = cp.Problem(cp.Minimize(0), [cp.norm(x) <= t])
        yield run_prox, ProxFunction.SECOND_ORDER_CONE, prob, v_map
