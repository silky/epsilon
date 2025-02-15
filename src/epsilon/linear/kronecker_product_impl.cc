#include "epsilon/linear/kronecker_product_impl.h"
#include "epsilon/vector/vector_util.h"
#include "epsilon/util/time.h"

namespace linear_map {

LinearMap::DenseMatrix KroneckerProductImpl::AsDense() const {
  DenseMatrix A = A_.impl().AsDense();
  DenseMatrix B = B_.impl().AsDense();
  DenseMatrix C(m(), n());

  for (int i = 0; i < A.rows(); i++) {
    for (int j = 0; j < A.cols(); j++) {
      C.block(i*B.rows(), j*B.cols(), B.rows(), B.cols()) = A(i,j)*B;
    }
  }

  return C;
}

LinearMap::SparseMatrix KroneckerProductImpl::AsSparse() const {
  DenseMatrix A = A_.impl().AsDense();
  DenseMatrix B = B_.impl().AsDense();
  SparseMatrix C(m(), n());

  {
    std::vector<Eigen::Triplet<double> > coeffs;
    for (int i = 0; i < A.rows(); i++) {
      for (int j = 0; j < A.cols(); j++) {
        if (A(i,j) == 0)
          continue;
        AppendBlockTriplets(A(i,j)*B, i*B.rows(), j*B.cols(), &coeffs);
      }
    }
    C.setFromTriplets(coeffs.begin(), coeffs.end());
  }

  return C;
}

LinearMapImpl::DenseVector KroneckerProductImpl::Apply(
    const LinearMapImpl::DenseVector& x) const {
  DenseMatrix X = ToMatrix(x, B_.impl().n(), A_.impl().n());
  return ToVector(
      A_.impl().ApplyMatrix(
          B_.impl().ApplyMatrix(X).transpose()).transpose());
}

bool KroneckerProductImpl::operator==(const LinearMapImpl& other) const {
  if (other.type() != KRONECKER_PRODUCT ||
      other.m() != m() ||
      other.n() != n())
    return false;

  auto const& K = static_cast<const KroneckerProductImpl&>(other);
  return K.A() == A() && K.B() == B();
}


}  // namespace linear_map
