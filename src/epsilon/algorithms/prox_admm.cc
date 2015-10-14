
#include "epsilon/algorithms/prox_admm.h"

#include <Eigen/OrderingMethods>
#include <Eigen/SparseQR>

#include "epsilon/affine/affine.h"
#include "epsilon/affine/affine_matrix.h"
#include "epsilon/affine/split.h"
#include "epsilon/expression/expression.h"
#include "epsilon/expression/expression_util.h"
#include "epsilon/prox/prox.h"
#include "epsilon/util/string.h"
#include "epsilon/vector/vector_operator.h"
#include "epsilon/vector/vector_util.h"

ProxADMMSolver::ProxADMMSolver(
    const Problem& problem,
    const SolverParams& params,
    std::unique_ptr<ParameterService> parameter_service)
    : problem_(problem),
      params_(params),
      parameter_service_(std::move(parameter_service)) {}

// TODO(mwytock): Dealing with constraints in the fashion: w/ vstack() and
// multiple calls to BuildAffineOperator() can be highly inefficient. We need a
// better mechanism, likely built on a more flexible BuildAffineOperator()
// implementation.
void ProxADMMSolver::InitConstraints() {
  for (int i = 0; i < problem_.constraint_size(); i++) {
    affine::BuildAffineOperator(
        problem_.constraint(i),
        "constr" + std::to_string(i),
        &A_, &b_);
  }
  m_ = A_.rows();
  n_ = A_.cols();
}

void ProxADMMSolver::InitProxOperators() {
  CHECK_EQ(Expression::ADD, problem_.objective().expression_type());
  N_ = problem_.objective().arg_size();

  for (int i = 0; i < N_; i++) {
    const Expression& f_expr = problem_.objective().arg(i);
    std::vector<std::string> var_ids;
    for (const Expression* expr : GetVariables(problem_.objective().arg(i)))
      var_ids.push_back(expr->variable().variable_id());

    // TODO(mwytock): Check that A'A is a scalar matrix and get alpha
    AT_.emplace_back(A_.ColBlock(var_ids).transpose());
    prox_.emplace_back(CreateProxOperator(1/params_.rho(), f_expr));
    prox_.back()->Init();
  }
}

void ProxADMMSolver::Init() {
  VLOG(2) << problem_.DebugString();
  InitConstraints();
  InitProxOperators();
  VLOG(1) << "Prox ADMM " << " m = " << m_ << " n = " << n_ << " N = " << N_;
}

void ProxADMMSolver::Solve() {
  Init();

  for (iter_ = 0; iter_ < params_.max_iterations(); iter_++) {
    x_prev_ = x_;
    u_ -= b_;
    for (int i = 0; i < N_; i++) {
      u_ += A_*x_[i];
      x_[i] = prox_[i]->Apply(AT_[i]*u_);
      u_ -= A_*x_[i];
    }

    if ((iter_+1) % params_.epoch_iterations() == 0) {
      ComputeResiduals();
      LogStatus();
      if (status_.state() == SolverStatus::OPTIMAL)
        break;
    }
  }

  UpdateLocalParameters();
  if (iter_ == params_.max_iterations())
      status_.set_state(SolverStatus::MAX_ITERATIONS_REACHED);
  UpdateStatus(status_);
}

void ProxADMMSolver::UpdateLocalParameters() {
  for (int i = 0; i < N_; i++) {
    for (const Expression* expr : GetVariables(problem_.objective().arg(i))) {
      const std::string& var_id = expr->variable().variable_id();
      uint64_t param_id = VariableParameterId(problem_id(), var_id);
      parameter_service_->Update(param_id, x_[i](var_id));
    }
  }
}

void ProxADMMSolver::ComputeResiduals() {
  SolverStatus::Residuals* r = status_.mutable_residuals();

  const double abs_tol = params_.abs_tol();
  const double rel_tol = params_.rel_tol();
  const double rho = params_.rho();

  BlockVector Ax_b = b_;
  double max_Ai_xi_norm = b_.norm();
  for (int i = 0; i < N_; i++) {
    BlockVector Ai_xi = A_*x_[i];
    max_Ai_xi_norm = fmax(max_Ai_xi_norm, Ai_xi.norm());
    Ax_b += Ai_xi;
  }

  double ATu_norm_squared = 0.0;
  double s_norm_squared = 0;
  BlockVector x_diff;
  for (int i = N_ - 2; i >= 0; i--) {
    x_diff += x_[i+1] - x_prev_[i+1];
    const double s_norm_i = (AT_[i]*A_*x_diff).norm();
    const double ATu_norm_i = (AT_[i]*u_).norm();
    s_norm_squared += s_norm_i*s_norm_i;
    ATu_norm_squared += ATu_norm_i*ATu_norm_i;
  }

  r->set_r_norm(Ax_b.norm());
  r->set_s_norm(rho*sqrt(s_norm_squared));
  r->set_epsilon_primal(abs_tol*sqrt(m_) + rel_tol*max_Ai_xi_norm);
  r->set_epsilon_dual(  abs_tol*sqrt(n_) +
                        rel_tol*rho*sqrt(ATu_norm_squared));

  if (r->r_norm() <= r->epsilon_primal() &&
      r->s_norm() <= r->epsilon_dual()) {
    status_.set_state(SolverStatus::OPTIMAL);
  } else {
    status_.set_state(SolverStatus::RUNNING);
  }

  status_.set_num_iterations(iter_);
}

void ProxADMMSolver::LogStatus() {
  const SolverStatus::Residuals& r = status_.residuals();
  VLOG(1) << StringPrintf(
      "iter=%d residuals primal=%.2e [%.2e] dual=%.2e [%.2e]",
      status_.num_iterations(),
      r.r_norm(),
      r.epsilon_primal(),
      r.s_norm(),
      r.epsilon_dual());
}
