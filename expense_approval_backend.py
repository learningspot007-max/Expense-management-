from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import SQLModel, Session, create_engine, Field, Relationship, select
from typing import Optional, List
from datetime import datetime
import uuid

# -----------------------
# Database setup
# -----------------------
engine = create_engine("sqlite:///database.db")


def get_session():
    with Session(engine) as session:
        yield session


# -----------------------
# Models
# -----------------------
class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    country: str
    currency: str

    users: List["User"] = Relationship(back_populates="company")


class UserRole(str):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str
    password: str  # demo only, use hashing in production!
    role: str
    company_id: int = Field(foreign_key="company.id")

    company: Optional[Company] = Relationship(back_populates="users")
    expenses: List["Expense"] = Relationship(back_populates="user")
    approvals: List["ApprovalRequest"] = Relationship(back_populates="approver")

    manager_id: Optional[int] = Field(default=None, foreign_key="user.id")
    manager: Optional["User"] = Relationship(sa_relationship_kwargs={"remote_side": "User.id"})


class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    amount: float
    currency: str
    category: str
    description: str
    date: datetime
    user_id: int = Field(foreign_key="user.id")

    user: Optional[User] = Relationship(back_populates="expenses")
    approvals: List["ApprovalRequest"] = Relationship(back_populates="expense")


class ApprovalRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    status: str = "pending"  # pending/approved/rejected
    step: int
    expense_id: int = Field(foreign_key="expense.id")
    approver_id: int = Field(foreign_key="user.id")

    expense: Optional[Expense] = Relationship(back_populates="approvals")
    approver: Optional[User] = Relationship(back_populates="approvals")


class ApprovalRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id")
    step: int
    approver_id: Optional[int] = Field(default=None, foreign_key="user.id")
    percentage_required: Optional[float] = None  # if set, requires % approvals
    hybrid: bool = False


# -----------------------
# Auth (demo only, tokens)
# -----------------------
security = HTTPBearer()
fake_tokens = {}  # token -> user_id


def create_token(user_id: int) -> str:
    token = str(uuid.uuid4())
    fake_tokens[token] = user_id
    return token


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session),
) -> User:
    token = credentials.credentials
    if token not in fake_tokens:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = fake_tokens[token]
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# -----------------------
# FastAPI setup
# -----------------------
app = FastAPI()


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


# -----------------------
# Routes
# -----------------------
@app.post("/signup")
def signup(company: str, country: str, email: str, password: str, session: Session = Depends(get_session)):
    # Demo: currency from country
    currency_map = {"US": "USD", "IN": "INR", "UK": "GBP"}
    currency = currency_map.get(country.upper(), "USD")

    new_company = Company(name=company, country=country, currency=currency)
    session.add(new_company)
    session.commit()
    session.refresh(new_company)

    admin = User(email=email, password=password, role=UserRole.ADMIN, company_id=new_company.id)
    session.add(admin)
    session.commit()
    session.refresh(admin)

    token = create_token(admin.id)
    return {"company": new_company.name, "admin_id": admin.id, "token": token}


@app.post("/login")
def login(email: str, password: str, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == email, User.password == password)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = create_token(user.id)
    return {"user_id": user.id, "role": user.role, "token": token}


@app.post("/users")
def create_user(email: str, password: str, role: str, manager_id: Optional[int] = None,
                current_user: User = Depends(get_current_user),
                session: Session = Depends(get_session)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can create users")

    new_user = User(email=email, password=password, role=role, company_id=current_user.company_id,
                    manager_id=manager_id)
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return {"id": new_user.id, "email": new_user.email, "role": new_user.role}


@app.post("/expenses")
def submit_expense(amount: float, currency: str, category: str, description: str,
                   current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    expense = Expense(amount=amount, currency=currency, category=category, description=description,
                      date=datetime.utcnow(), user_id=current_user.id)
    session.add(expense)
    session.commit()
    session.refresh(expense)

    # Create approval requests per company rules
    rules = session.exec(select(ApprovalRule).where(ApprovalRule.company_id == current_user.company_id)).all()
    if not rules and current_user.manager_id:  # fallback: manager approval
        ar = ApprovalRequest(step=1, expense_id=expense.id, approver_id=current_user.manager_id)
        session.add(ar)
    else:
        for rule in rules:
            if rule.approver_id:
                ar = ApprovalRequest(step=rule.step, expense_id=expense.id, approver_id=rule.approver_id)
                session.add(ar)

    session.commit()
    return {"expense_id": expense.id, "status": "submitted"}


@app.get("/approvals")
def get_approvals(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    approvals = session.exec(select(ApprovalRequest).where(ApprovalRequest.approver_id == current_user.id)).all()
    return approvals


@app.post("/approvals/{approval_id}")
def act_on_approval(approval_id: int, action: str,
                    current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    approval = session.get(ApprovalRequest, approval_id)
    if not approval or approval.approver_id != current_user.id:
        raise HTTPException(status_code=404, detail="Approval not found")

    if action not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    approval.status = action
    session.add(approval)
    session.commit()
    return {"approval_id": approval.id, "status": approval.status}


@app.get("/company/expenses")
def list_company_expenses(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can view company expenses")
    expenses = session.exec(select(Expense).where(Expense.user_id.in_(
        [u.id for u in current_user.company.users]
    ))).all()
    return expenses
