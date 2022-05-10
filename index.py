from ast import alias
from email.policy import default
from fastapi import HTTPException, status, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from distutils.util import execute
import secrets, string, random
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Float, select
from sqlalchemy.orm import declarative_base, relationship, joinedload
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.sql import func
from uuid import uuid4;

engine = engine = create_engine('postgresql://postgres:postgres@localhost/kriptokitty')


conn = engine.connect()
Base = declarative_base()

# Generate Random Strong Password
def generate_pass():
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for i in range(20))
    return password

class Withdrawals(Base):
    __tablename__ = 'withdrawals'
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'))
    asset_id = Column(ForeignKey('assets.id'))
    destination_address = Column(String, nullable=False)
    status = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    blockchain_hash = Column(String, default=str(uuid4()))
    network_fee = Column(String, default=random.uniform(10.5, 100.5))
    created_on = Column(DateTime(timezone=True), default=func.now())
    user = relationship("User", back_populates="assets")
    asset = relationship("Asset", back_populates="users")
    # proxies
    asset_code = association_proxy(target_collection='asset', attr='iso_code')
    user_email = association_proxy(target_collection='user', attr='email')

class Wallets(Base):
    __tablename__ = 'wallets'
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'))
    asset_id = Column(ForeignKey('assets.id'))
    address = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    created_on = Column(DateTime(timezone=True), default=func.now())
    user = relationship("User", back_populates="assets_wallet")
    asset = relationship("Asset", back_populates="users_wallet")
    # proxies
    asset_code = association_proxy(target_collection='asset', attr='iso_code')
    user_email = association_proxy(target_collection='user', attr='email')

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False)
    encrypted_password = Column(String(255), default=generate_pass)
    api_key = Column(String(255), default=str(uuid4()))
    created_on = Column(DateTime(timezone=True), default=func.now())
    assets = relationship("Withdrawals", back_populates="user")
    assets_wallet = relationship("Wallets", back_populates="user")

class Asset(Base):
    __tablename__ = 'assets'
    id = Column(Integer, primary_key=True)
    iso_code = Column(String)
    users = relationship("Withdrawals", back_populates="asset")
    users_wallet = relationship("Wallets", back_populates="asset")

# Create the tables in the database
Base.metadata.create_all(engine)

# # Here we are going to insert some data to test 
from sqlalchemy.orm import Session
with Session(bind=engine) as session:
    # Truncate all tables and restart the value of Primary Key
    session.execute('''TRUNCATE TABLE users, assets, withdrawals, wallets RESTART IDENTITY''')
    session.commit()

    user1 = User(email="baseer@email.com")
    user2 = User(email="baheer@email.com")

    asset1 = Asset(iso_code="ETH")
    asset2 = Asset(iso_code="BTC")
    asset3 = Asset(iso_code="DOGE")

    session.add_all([user1, user2, asset1, asset2, asset3])
    session.commit()

    withdrawals1 = Withdrawals(user_id=user1.id, asset_id=asset1.id, destination_address="SEB 56473434", status="COMPLETED", amount=202.4)
    withdrawals2 = Withdrawals(user_id=user2.id, asset_id=asset2.id, destination_address="SWED 56473434", status="FAILED", amount=32.4)
    withdrawals3 = Withdrawals(user_id=user1.id, asset_id=asset3.id, destination_address="SWED 56567890", status="COMPLETED", amount=356.4)

    wallet1 = Wallets(user_id=user1.id, asset_id=asset1.id, address = "SEB 878954", amount=200)
    wallet2 = Wallets(user_id=user1.id, asset_id=asset1.id, address = "SEB 878954", amount=200)
    session.add_all([withdrawals1, withdrawals2, withdrawals3, wallet1, wallet2])
    session.commit()


from typing import List
from pydantic import BaseModel, Field

class UserBase(BaseModel):
    email: str = Field(alias='user_email')
    
    class Config:
        orm_mode = True
        allow_population_by_field_name = True

class AssetBase(BaseModel):
    iso_code: str = Field(alias='iso_code')

    class Config:
        orm_mode = True
        allow_population_by_field_name = True

class UserSchema(UserBase):
    assets: List[AssetBase]

class AssetSchema(AssetBase):
    users: List[UserBase]

class WalletBase(BaseModel):
    user_id: int = Field(alias='user_id')
    asset_id: int = Field(alias='asset_id')
    address: str = Field(alias='source_address')
    amount: float = Field(alias='amount')
    
    class Config:
        orm_mode = True
        allow_population_by_field_name = True

class WithdrawalBase(BaseModel):
    user_id: int = Field(alias='user_id')
    asset_id: int = Field(alias='asset_id')
    destination_address: str = Field(alias='destination_address')
    status: str = Field(alias='status')
    amount: float = Field(alias='amount')
    network_fee: float = Field(alias='network_fee')

    class Config:
        orm_mode = True
        allow_population_by_field_name = True


from fastapi import FastAPI, Depends

app = FastAPI(title="Kriptokitty")

def get_db():
    db = Session(bind=engine)
    try:
        yield db
    finally:
        db.close()

@app.get("/users/{id}")
async def get_user(id: int, db: Session = Depends(get_db)):
    db_user = session.get(User, id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found",)
    return db_user

@app.get("/users")
async def get_users(db: Session = Depends(get_db)):
    db_users = db.query(User).options(joinedload(User.assets)).all()
    if not db_users:
        raise HTTPException(status_code=404, detail="User not found",)
    return db_users

@app.post("/users/")
async def create_user(user: UserBase, db: Session = Depends(get_db)):
    user_add = User(email=user.email)
    session.add_all([user_add])
    session.commit()
    obj = session.query(User).order_by(User.id.desc()).first()
    return obj

@app.patch("/users/{id}")
async def update_user(id: int, user: UserBase):
    db_user = session.get(User, id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found",)
    user_data = user.dict(exclude_unset=True)
    for key, value in user_data.items():
        setattr(db_user, key, value)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@app.post("/transactions", status_code=status.HTTP_201_CREATED)
async def create_transaction(withdrawals:WithdrawalBase, response: Response, db: Session = Depends(get_db)):
    find_user_id = db.query(Wallets).where(Wallets.user_id == withdrawals.user_id).all()
    if not find_user_id:
        raise HTTPException(status_code=404, detail="User ID not found",)
    
    find_asset_id = db.query(Wallets).where(Wallets.asset_id == withdrawals.asset_id).all()
    if not find_asset_id:
        raise HTTPException(status_code=404, detail="Asset ID not found",)
    
    withdrawals_amount = withdrawals.amount
    for row in find_user_id:
        if withdrawals.amount > row.amount:
            raise HTTPException(status_code=400, detail="Amount Exceeds the total Wallet Amount",)

    withdrawal_add = Withdrawals(user_id=withdrawals.user_id, asset_id=withdrawals.asset_id, destination_address=withdrawals.destination_address, status=withdrawals.status, amount=withdrawals.amount, network_fee=withdrawals.network_fee)
    session.add_all([withdrawal_add])
    session.commit()
    response.details = "Trasaction created!"
    obj = session.query(Withdrawals).order_by(Withdrawals.id.desc()).first()
    return obj.id, obj.blockchain_hash, obj.network_fee, obj.created_on, obj.status


@app.get("/transactions/{id}")
async def get_transaction(id: int, db: Session = Depends(get_db)):
    withdrawal = session.get(Withdrawals, id)
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Transaction not found",)
    return withdrawal.id, withdrawal.blockchain_hash, withdrawal.network_fee, withdrawal.created_on, withdrawal.status

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content = {"message": "Invalid parameters provided"},
    )

import uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)