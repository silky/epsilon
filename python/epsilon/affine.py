"""Operations on LinearMaps."""
import numpy as np
import scipy.sparse as sp

from epsilon import linear_map
from epsilon.error import LinearMapError
from epsilon.expression_pb2 import Expression, LinearMap
from epsilon.expression_util import *

def dense_type():
    return LinearMapType(LinearMap(linear_map_type=LinearMap.DENSE_MATRIX))

def multiply_kronecker(K, A):
    KA = LinearMapType(K.linear_map.arg[0])
    KB = LinearMapType(K.linear_map.arg[1])
    if A.scalar and (KA.scalar or KB.scalar):
        return K.copy()
    return dense_type()

def add_kronecker(K, A):
    raise LinearMapError("not implemented", K, A)

class LinearMapType(object):
    """Handle type conversion for linear maps."""
    def __init__(self, linear_map):
        self.linear_map = linear_map

    @property
    def basic(self):
        return self.linear_map.linear_map_type in (
            LinearMap.DENSE_MATRIX,
            LinearMap.SPARSE_MATRIX,
            LinearMap.DIAGONAL_MATRIX,
            LinearMap.SCALAR)

    @property
    def diagonal(self):
        return self.linear_map.linear_map_type in (
            LinearMap.DIAGONAL_MATRIX,
            LinearMap.SCALAR)

    @property
    def scalar(self):
        return self.linear_map.linear_map_type == LinearMap.SCALAR

    @property
    def kronecker_product(self):
        return self.linear_map.linear_map_type == LinearMap.KRONECKER_PRODUCT

    def eval_ops(self):
        if self.linear_map.linear_map_type == LinearMap.TRANSPOSE:
            A = LinearMapType(self.linear_map.arg[0])
            return A.eval_ops()
        return self

    def copy(self):
        linear_map = LinearMap()
        linear_map.CopyFrom(self.linear_map)
        return LinearMapType(linear_map)

    def promote(self, other):
        assert self.basic
        assert other.basic
        if self.linear_map.linear_map_type > other.linear_map.linear_map_type:
            self.linear_map.linear_map_type = other.linear_map.linear_map_type
        return self

    def __add__(self, B):
        assert isinstance(B, LinearMapType)

        if self.basic and B.basic:
            return self.copy().promote(B)

        if self.kronecker_product:
            return add_kronecker(self, B)
        if B.kronecker_pdocut:
            return add_kronecker(B, self)

        return dense_type()

    def __mul__(self, B):
        if isinstance(B, AffineExpression):
            return B.__rmul__(self)
        assert isinstance(B, LinearMapType)

        if self.basic and B.basic:
            return self.copy().promote(B)

        if self.kronecker_product:
            return multiply_kronecker(self, B)
        if B.kronecker_product:
            return multiply_kronecker(B, self)

        return dense_type()

class AffineExpression(object):
    def __init__(self, linear_maps):
        self.linear_maps = linear_maps

    @property
    def diagonal(self):
        return (len(self.linear_maps) == 1 and
                self.linear_maps.values()[0].diagonal)

    @property
    def scalar(self):
        return (len(self.linear_maps) == 1 and
                self.linear_maps.values()[0].scalar)

    def __rmul__(self, A):
        assert isinstance(A, LinearMapType)
        C = AffineExpression(self.linear_maps.copy())
        for var_id, Bi in self.linear_maps.items():
            C.linear_maps[var_id] = A*Bi
        return C

    def __add__(self, B):
        assert isinstance(B, AffineExpression)
        C = AffineExpression(self.linear_maps.copy())
        for var_id, Bi in B.linear_maps.items():
            if var_id not in self.linear_maps:
                C.linear_maps[var_id] = Bi
            else:
                C.linear_maps[var_id] += Bi
        return C

# TODO(mwytock): memoize
def get_affine_expr(expr):
    if expr.expression_type == Expression.CONSTANT:
        # TODO(mwytock): Keep track of constant terms if needed
        return AffineExpression({})

    elif expr.expression_type == Expression.VARIABLE:
        return AffineExpression({
            expr.variable.variable_id:
            LinearMapType(linear_map.identity(dim(expr)))})

    elif expr.expression_type == Expression.ADD:
        return reduce(lambda A,B: A+B,
                      (get_affine_expr(arg) for arg in expr.arg))

    elif expr.expression_type == Expression.LINEAR_MAP:
        A = LinearMapType(expr.linear_map)
        A = A.eval_ops()
        return A*get_affine_expr(only_arg(expr))

    elif expr.expression_type == Expression.RESHAPE:
        return get_affine_expr(only_arg(expr))

    raise ExpressionError("Unkonwn expression type", expr)


def is_diagonal(expr):
    return get_affine_expr(expr).diagonal

def is_scalar(expr):
    return get_affine_expr(expr).scalar
