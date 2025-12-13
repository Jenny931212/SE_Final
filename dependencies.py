# dependencies.py

from fastapi import Request
from fastapi.exceptions import HTTPException

# 依賴函式：取得目前登入的使用者
def get_current_user(request: Request):
    user_id = request.session.get("user")
    #for not-login user, user_id will be None
    return user_id

# 依賴函式：取得目前登入的角色
def get_current_role(request: Request):
    return request.session.get("role")
    
# 依賴函式：檢查角色權限
def checkRole(requiredRole:str):
    def checker(request: Request):
        user_role = request.session.get("role")
        if user_role == requiredRole:
            return True
        else:
            # 這裡需要 HTTPException，確保您在 main.py 和 issueRoute.py 中引入了它
            raise HTTPException(status_code=401, detail="Not authenticated") 
    return checker