"""角色资产库 API（M5 ★核心）：人物子库 + 角色资产 + 一致性绑定。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Character, CharacterLibrary, Project, User
from ..schemas import (CharacterCreate, CharacterImageIn, CharacterOut,
                       CharacterUpdate, LibraryCreate, LibraryOut, LibraryUpdate)
from .ai_requests import gate_request

router = APIRouter(tags=["角色资产库"])


# ---------- 人物子库（按项目管理） ----------
@router.get("/character-libraries", response_model=list[LibraryOut], summary="人物子库列表")
def list_libraries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(CharacterLibrary).filter(
        CharacterLibrary.user_id == user.id).order_by(CharacterLibrary.id.desc()).all()


@router.post("/character-libraries", response_model=LibraryOut, summary="创建人物子库")
def create_library(data: LibraryCreate, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    lib = CharacterLibrary(user_id=user.id, **data.model_dump())
    db.add(lib)
    db.commit()
    db.refresh(lib)
    return lib


@router.put("/character-libraries/{lib_id}", response_model=LibraryOut, summary="重命名/归档人物子库")
def update_library(lib_id: int, data: LibraryUpdate,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lib = db.get(CharacterLibrary, lib_id)
    if not lib or lib.user_id != user.id:
        raise HTTPException(status_code=404, detail="子库不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(lib, k, v)
    db.commit()
    db.refresh(lib)
    return lib


@router.post("/character-libraries/{lib_id}/copy", response_model=LibraryOut, summary="复制子库（复制整组角色）")
def copy_library(lib_id: int, name: str = "", user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    lib = db.get(CharacterLibrary, lib_id)
    if not lib or lib.user_id != user.id:
        raise HTTPException(status_code=404, detail="子库不存在")
    new_lib = CharacterLibrary(user_id=user.id, name=name or f"{lib.name}（副本）",
                               desc=lib.desc, project_ids=list(lib.project_ids or []),
                               is_shared=lib.is_shared)
    db.add(new_lib)
    db.flush()
    for c in db.query(Character).filter(Character.library_id == lib.id).all():
        db.add(Character(library_id=new_lib.id, user_id=user.id, name=c.name, desc=c.desc,
                         appearance=c.appearance, outfit=c.outfit, personality=c.personality,
                         ref_images=list(c.ref_images or []),
                         expression_set=list(c.expression_set or []),
                         voice_id=c.voice_id, lora_version=c.lora_version))
    db.commit()
    db.refresh(new_lib)
    return new_lib


@router.delete("/character-libraries/{lib_id}", summary="删除子库（二次确认；返回引用清单）")
def delete_library(lib_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    lib = db.get(CharacterLibrary, lib_id)
    if not lib or lib.user_id != user.id:
        raise HTTPException(status_code=404, detail="子库不存在")
    chars = db.query(Character).filter(Character.library_id == lib_id).all()
    char_ids = [c.id for c in chars]
    from ..models import Shot
    refs = [s for s in db.query(Shot).all() if set(s.char_ref_ids or []) & set(char_ids)]
    db.query(Character).filter(Character.library_id == lib_id).delete(synchronize_session=False)
    db.delete(lib)
    db.commit()
    return {"message": "已删除", "deleted_characters": len(char_ids),
            "referenced_shots": [s.shot_no for s in refs]}


# ---------- 角色 ----------
@router.get("/character-libraries/{lib_id}/characters", response_model=list[CharacterOut],
            summary="子库内角色列表")
def list_characters(lib_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    lib = db.get(CharacterLibrary, lib_id)
    if not lib or lib.user_id != user.id:
        raise HTTPException(status_code=404, detail="子库不存在")
    return db.query(Character).filter(Character.library_id == lib_id,
                                      Character.status == "active").all()


@router.get("/projects/{project_id}/characters", response_model=list[CharacterOut],
            summary="项目引用角色汇总")
def project_characters(project_id: int, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    libs = db.query(CharacterLibrary).filter(CharacterLibrary.user_id == user.id).all()
    selected = [l.id for l in libs if project_id in (l.project_ids or [])]
    all_libs = selected or [l.id for l in libs]
    return db.query(Character).filter(Character.library_id.in_(all_libs)).all() if all_libs else []


@router.post("/characters", response_model=CharacterOut, summary="创建角色")
def create_character(data: CharacterCreate, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    lib = db.get(CharacterLibrary, data.library_id)
    if not lib or lib.user_id != user.id:
        raise HTTPException(status_code=404, detail="人物子库不存在")
    c = Character(user_id=user.id, library_id=data.library_id, name=data.name, desc=data.desc,
                  appearance=data.appearance, outfit=data.outfit, personality=data.personality,
                  voice_id=data.voice_id or "")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/characters/{char_id}", response_model=CharacterOut, summary="编辑角色")
def update_character(char_id: int, data: CharacterUpdate,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Character, char_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="角色不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/characters/{char_id}", summary="删除角色")
def delete_character(char_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    c = db.get(Character, char_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="角色不存在")
    db.delete(c)
    db.commit()
    return {"message": "已删除"}


@router.post("/characters/{char_id}/images", summary="生成角色三视图 + 表情集（过闸口）")
def generate_images(char_id: int, data: CharacterImageIn,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Character, char_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="角色不存在")
    params = {"character_id": c.id, "count": 3}
    return gate_request(db, user, module="character", project_id=None, params=params,
                        batch_count=1, session_id=data.session_id)
