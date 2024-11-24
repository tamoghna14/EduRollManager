import random
import string
from io import BytesIO
from fastapi import FastAPI, Form, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from PIL import Image, ImageDraw, ImageFont
from database import SessionLocal, engine, Base
from models import User

# Initialize the database
Base.metadata.create_all(bind=engine)

# FastAPI app and template setup
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper function to generate random CAPTCHA text
def generate_captcha_text(length=5):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Route to generate and display CAPTCHA image
@app.get("/captcha")
async def get_captcha():
    captcha_text = generate_captcha_text()
    
    # Save the CAPTCHA text to the app's state for temporary storage (not recommended for production)
    app.state.captcha_text = captcha_text

    # Generate CAPTCHA image
    img = Image.new('RGB', (150, 50), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    d.text((10, 10), captcha_text, font=font, fill=(0, 0, 0))

    # Convert the image to bytes
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return StreamingResponse(img_byte_arr, media_type="image/png")

# Home page (index) with registration form
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, message: str = ""):
    return templates.TemplateResponse("index.html", {"request": request, "message": message})

# Add user route with CAPTCHA validation
@app.post("/add_user/")
async def add_user(name: str = Form(...), roll_no: int = Form(...), captcha: str = Form(...), db: Session = Depends(get_db)):
    # Check if CAPTCHA is correct
    if captcha != app.state.captcha_text:
        message = "CAPTCHA incorrect. Please try again."
        return RedirectResponse(url=f"/?message={message}", status_code=303)

    # Check if the user already exists
    existing_user = db.query(User).filter((User.name == name) | (User.roll_no == roll_no)).first()
    if existing_user:
        message = "User already registered with this name or roll number."
    else:
        new_user = User(name=name, roll_no=roll_no)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        message = "User successfully added!"
    return RedirectResponse(url=f"/?message={message}", status_code=303)

# Search user page with CAPTCHA form
@app.get("/search_user", response_class=HTMLResponse)
async def search_user(request: Request):
    return templates.TemplateResponse("search_user.html", {"request": request})

# Search result route with CAPTCHA validation
@app.post("/search_user_result/")
async def search_user_result(request: Request, search_name: str = Form(...), captcha: str = Form(...), db: Session = Depends(get_db)):
    # Check CAPTCHA
    if captcha != app.state.captcha_text:
        return templates.TemplateResponse("search_user.html", {"request": request, "error": "CAPTCHA incorrect. Please try again."})

    # Perform search
    user = db.query(User).filter(User.name == search_name).first()
    if user:
        return templates.TemplateResponse("get_user.html", {"request": request, "user": user})
    return templates.TemplateResponse("get_user.html", {"request": request, "error": "User not found"})

# User profile page
@app.get("/get_user", response_class=HTMLResponse)
async def get_user(request: Request, name: str = ""):
    return templates.TemplateResponse("get_user.html", {"request": request, "name": name})
