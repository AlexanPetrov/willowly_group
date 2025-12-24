"""Database CRUD operations for user management."""

from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError

from . import db
from .models import User
from .logger import logger
from .config import settings


# ==================== Helper Functions ====================

def _create_user_snapshot(user: User) -> User:
    """Create a detached snapshot of a user before deletion."""
    snapshot = User()
    snapshot.id = user.id
    snapshot.name = user.name
    snapshot.email = user.email
    snapshot.hashed_password = user.hashed_password
    snapshot.is_active = user.is_active
    snapshot.created_at = user.created_at
    return snapshot


# ==================== Single User Operations ====================


async def insert_user(name: str, email: str, hashed_password: str) -> User:
    """Insert a new user with hashed password. Raises ValueError on duplicate email."""
    async with db.async_session() as session:
        try:
            async with session.begin():
                user = User(name=name, email=email, hashed_password=hashed_password)
                session.add(user)
            await session.refresh(user) # To update ORM object
            return user
        except IntegrityError as e:
            await session.rollback()
            logger.debug(f"Duplicate email rejected: {email}")
            raise ValueError("duplicate email") from e


async def select_user_by_email(email: str) -> User | None:
    """Retrieve a user by email address."""
    async with db.async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalars().first()


async def select_user(user_id: int) -> User | None:
    """Retrieve a user by ID."""
    async with db.async_session() as session:
        result = await session.get(User, user_id)
        return result


async def delete_user(user_id: int) -> User | None:
    """Delete a user by ID and return a snapshot of the deleted user."""
    async with db.async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return None
        try:
            snapshot = _create_user_snapshot(user)
            await session.delete(user)
            await session.commit()
            return snapshot
        except Exception:
            await session.rollback()
            logger.error(f"Failed to delete user id={user_id}", exc_info=True)
            raise


async def list_users(
    skip: int,
    limit: int,
    email: str | None = None, # Filter by email
    email_domain: str | None = None, # Filter by email domain
    sort: str = "id",
    order: str = "asc",
) -> tuple[list[User], int]:
    """List users with optional filters, sorting, and pagination. Returns list of users and total count."""
    async with db.async_session() as session:
        try:
            # Optional filters
            conditions: list = []
            if email:
                conditions.append(User.email == email)
            if email_domain:
                conditions.append(User.email.ilike(f"%@{email_domain}"))
            # Total count w/ same filters
            count_stmt = select(func.count()).select_from(User)
            if conditions:
                count_stmt = count_stmt.where(*conditions)
            count_result = await session.execute(count_stmt)
            total = count_result.scalar() or 0
            # Fetch paginated users with filters and sorting
            stmt = select(User)
            if conditions:
                stmt = stmt.where(*conditions)
            # Apply sorting
            sort_column = getattr(User, sort, User.id)
            if order == "desc":
                stmt = stmt.order_by(sort_column.desc())
            else:
                stmt = stmt.order_by(sort_column.asc())
            stmt = stmt.offset(skip).limit(limit) # Pagination
            result = await session.execute(stmt)
            users = result.scalars().all()
            logger.debug(f"Query executed: returned {len(users)} users out of {total} total")
            return users, total
        except Exception:
            await session.rollback()
            logger.error("Failed to list users", exc_info=True)
            raise


# ==================== Batch Operations ====================

async def insert_users(items: list[dict]) -> list[User]:
    """Insert multiple users in a single transaction, processing in chunks for memory efficiency.
    All-or-nothing: either all users are inserted or none are (atomic operation).
    Raises ValueError on duplicate email.
    
    Each item dict must contain: name, email, and hashed_password.
    """
    if not items:
        return []
    
    # Validate that all items have required fields
    for item in items:
        if 'hashed_password' not in item:
            raise ValueError("Each user item must include 'hashed_password' field")
    
    total_chunks = (len(items) + settings.CHUNK_SIZE - 1) // settings.CHUNK_SIZE
    logger.debug(f"Processing {len(items)} users in {total_chunks} chunks of {settings.CHUNK_SIZE} (atomic transaction)")
    
    # Single session for entire batch - atomic transaction
    async with db.async_session() as session:
        try:
            async with session.begin():  # Single transaction for entire batch
                all_users = []
                
                # Process in chunks for memory efficiency
                for i in range(0, len(items), settings.CHUNK_SIZE):
                    chunk = items[i:i + settings.CHUNK_SIZE]
                    chunk_num = (i // settings.CHUNK_SIZE) + 1
                    logger.debug(f"Processing chunk {chunk_num}/{total_chunks} ({len(chunk)} users)")
                    
                    objs = [
                        User(
                            name=item["name"],
                            email=item["email"],
                            hashed_password=item["hashed_password"],
                        )
                        for item in chunk
                    ]
                    session.add_all(objs)
                    all_users.extend(objs)
                    
                    logger.debug(f"Chunk {chunk_num}/{total_chunks} staged")
                
                # Transaction commits here automatically (or rolls back on error)
            
            # Refresh all objects to populate IDs after commit
            for obj in all_users:
                await session.refresh(obj)
            
            logger.debug(f"Batch insert completed: {len(all_users)} users created")
            return all_users
            
        except IntegrityError as e:
            # Transaction automatically rolled back
            logger.error(f"Batch insert failed: duplicate email (transaction rolled back)")
            raise ValueError("duplicate email") from e
        except Exception as e:
            logger.error(f"Batch insert failed: {str(e)} (transaction rolled back)", exc_info=True)
            raise


async def delete_users(ids: list[int]) -> list[User]:
    """Delete multiple users in a single transaction, processing in chunks for memory efficiency.
    All-or-nothing: either all users are deleted or none are (atomic operation).
    Returns snapshots of deleted users.
    """
    if not ids:
        return []
    
    total_chunks = (len(ids) + settings.CHUNK_SIZE - 1) // settings.CHUNK_SIZE
    logger.debug(f"Processing {len(ids)} deletions in {total_chunks} chunks of {settings.CHUNK_SIZE} (atomic transaction)")
    
    # Single session for entire batch - atomic transaction
    async with db.async_session() as session:
        try:
            async with session.begin():  # Single transaction for entire batch
                all_deleted = []
                
                # Process in chunks for memory efficiency
                for i in range(0, len(ids), settings.CHUNK_SIZE):
                    chunk = ids[i:i + settings.CHUNK_SIZE]
                    chunk_num = (i // settings.CHUNK_SIZE) + 1
                    logger.debug(f"Processing chunk {chunk_num}/{total_chunks} ({len(chunk)} users)")
                    
                    result = await session.execute(select(User).where(User.id.in_(chunk)))
                    users = result.scalars().all()
                    
                    if users:
                        # Take snapshots before deletion with all fields
                        deleted = []
                        for u in users:
                            snapshot = _create_user_snapshot(u)
                            deleted.append(snapshot)
                            await session.delete(u)
                        all_deleted.extend(deleted)
                        logger.debug(f"Chunk {chunk_num}/{total_chunks} staged: {len(users)} users")
                
                # Transaction commits here automatically (or rolls back on error)
            
            logger.debug(f"Batch delete completed: {len(all_deleted)} users deleted")
            return all_deleted
            
        except Exception as e:
            # Transaction automatically rolled back
            logger.error(f"Batch delete failed: {str(e)} (transaction rolled back)", exc_info=True)
            raise RuntimeError(f"Failed to delete users: {str(e)}") from e


# ==================== Search Operations ====================

async def search_users(
    query: str,
    skip: int,
    limit: int,
    sort: str = "id",
    order: str = "asc",
) -> tuple[list[User], int]:
    """Search users by name or email containing the query string."""
    async with db.async_session() as session:
        try:
            # Escape special LIKE characters (%, _, \) to prevent unintended wildcards
            escaped_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            search_pattern = f"%{escaped_query}%"
            # Search condition: name OR email contains query
            search_condition = or_(
                User.name.ilike(search_pattern, escape="\\"),
                User.email.ilike(search_pattern, escape="\\")
            )
            
            # Count total matching users
            count_stmt = select(func.count()).select_from(User).where(search_condition)
            count_result = await session.execute(count_stmt)
            total = count_result.scalar() or 0
            
            # Fetch paginated results with sorting
            stmt = select(User).where(search_condition)
            sort_column = getattr(User, sort, User.id)
            if order == "desc":
                stmt = stmt.order_by(sort_column.desc())
            else:
                stmt = stmt.order_by(sort_column.asc())
            stmt = stmt.offset(skip).limit(limit)
            result = await session.execute(stmt)
            users = result.scalars().all()
            logger.debug(f"Search query executed: found {len(users)} users (total matches: {total})")
            return users, total
        except Exception as e:
            logger.error(f"Search query failed for term '{query}': {str(e)}", exc_info=True)
            raise
