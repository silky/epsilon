
#include "epsilon/algorithms/prox_admm.h"

#include <Eigen/OrderingMethods>
#include <Eigen/SparseQR>

#include "epsilon/affine/affine.h"
#include "epsilon/expression/expression.h"
#include "epsilon/expression/expression_util.h"
#include "epsilon/prox/prox.h"
#include "epsilon/util/logging.h"
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

void ProxADMMSolver::InitConstraints() {
  for (int i = 0; i < problem_.constraint_size(); i++) {
    const Expression& constr = problem_.constraint(i);
    CHECK_EQ(Expression::INDICATOR, constr.expression_type());
    CHECK_EQ(Cone::ZERO, constr.cone().cone_type());
    CHECK_EQ(1, constr.arg_size());
    affine::BuildAffineOperator(
        problem_.constraint(i).arg(0),
        affine::constraint_key(i),
        &A_, &b_);
    u_(affine::constraint_key(i)) = BlockVector::DenseVector::Zero(
        GetDimension(problem_.constraint(i).arg(0)));
  }
  AT_ = A_.Transpose();
  m_ = A_.m();
  n_ = A_.n();
}

void ProxADMMSolver::InitProxOperators() {
  CHECK_EQ(Expression::ADD, problem_.objective().expression_type());
  N_ = problem_.objective().arg_size();
  x_.resize(N_);
  y_.resize(N_);

  // See TODO below
  CHECK_EQ(1, params_.rho());
  const double sqrt_rho = sqrt(params_.rho());

  for (int i = 0; i < N_; i++) {
    const Expression& f_expr = problem_.objective().arg(i);

    AffineOperator H;
    for (int i = 0; i < f_expr.arg_size(); i++) {
      affine::BuildAffineOperator(
          f_expr.arg(i),
          affine::arg_key(i),
          &H.A, &H.b);
    }

    AffineOperator A;
    std::set<std::string> constr_vars = A_.col_keys();
    for (const Expression* expr : GetVariables(f_expr)) {
      const std::string& var_id = expr->variable().variable_id();
      if (constr_vars.find(var_id) == constr_vars.end())
        continue;
      for (auto iter : A_.col(var_id)) {
        A.A(iter.first, var_id) = sqrt_rho*iter.second;
      }
    }

    ProxFunction::Type type = f_expr.prox_function().prox_function_type();
    bool epigraph = f_expr.prox_function().epigraph();
    VLOG(2) << "prox " << i << ", initializing "
            << ProxFunction::Type_Name(type);
    prox_.emplace_back(CreateProxOperator(type, epigraph));
    prox_.back()->Init(ProxOperatorArg(f_expr.prox_function(), H, A));

    // TODO(mwytock): This is scaled by rho now, figure out what to do here
    AiT_.push_back(A.A.Transpose());
  }
}

void ProxADMMSolver::Init() {
  VLOG(3) << problem_.DebugString();
  InitConstraints();
  InitProxOperators();

  VLOG(1) << "Prox ADMM, m = " << m_ << ", n = " << n_ << ", N = " << N_;
  VLOG(2) << "A:\n" << A_.DebugString() << "\n"
          << "b:\n" << b_.DebugString();
}

void ProxADMMSolver::Solve() {
  Init();

  for (iter_ = 0; iter_ < params_.max_iterations(); iter_++) {
    y_prev_ = y_;

    u_ -= b_;
    for (int i = 0; i < N_; i++)
      u_ -= y_[i];

    for (int i = 0; i < N_; i++) {
      u_ += y_[i];
      x_[i] = prox_[i]->Apply(u_);
      y_[i] = A_*x_[i];
      u_ -= y_[i];
      VLOG(2) << "x[" << i << "]: " << x_[i].DebugString();
    }
    VLOG(2) << "u: " << u_.DebugString();

    if (iter_ % params_.epoch_iterations() == 0) {
      ComputeResiduals();
      if (status_.state() == SolverStatus::OPTIMAL)
        break;
    }

    if (iter_ % params_.log_iterations() == 0) {
      LogStatus();
    }
  }

  if (iter_ == params_.max_iterations()) {
    ComputeResiduals();
    status_.set_state(SolverStatus::MAX_ITERATIONS_REACHED);
  }

  LogStatus();
  UpdateParameters();
  UpdateStatus(status_);
}

void ProxADMMSolver::UpdateParameters() {
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

  VLOG(3) << "compute r norm";
  BlockVector Ax_b = b_;
  double max_Ai_xi_norm = b_.norm();
  for (int i = 0; i < N_; i++) {
    BlockVector Ai_xi = A_*x_[i];
    max_Ai_xi_norm = fmax(max_Ai_xi_norm, Ai_xi.norm());
    Ax_b += Ai_xi;
  }

  VLOG(3) << "compute s norm";
  double s_norm_squared = 0;
  BlockVector Ax_diff;
  for (int i = N_ - 2; i >= 0; i--) {
    Ax_diff += y_[i+1] - y_prev_[i+1];
    const double s_norm_i = (AiT_[i]*Ax_diff).norm();
    s_norm_squared += s_norm_i*s_norm_i;
  }

  VLOG(3) << "set residuals";
  r->set_r_norm(Ax_b.norm());
  r->set_s_norm(rho*sqrt(s_norm_squared));
  r->set_epsilon_primal(abs_tol*sqrt(m_) + rel_tol*max_Ai_xi_norm);
  r->set_epsilon_dual(  abs_tol*sqrt(n_) + rel_tol*rho*(AT_*u_).norm());

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
  std::string status = StringPrintf(
      "iter=%d residuals primal=%.2e [%.2e] dual=%.2e [%.2e]",
      status_.num_iterations(),
      r.r_norm(),
      r.epsilon_primal(),
      r.s_norm(),
      r.epsilon_dual());
  VLOG(1) << status;
  LogVerbose(status);
}
