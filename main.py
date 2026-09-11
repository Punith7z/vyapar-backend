from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
from google import genai
from google.genai import types

app = FastAPI()

# Enable CORS for the mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ParseBillRequest(BaseModel):
    ocrText: str

class ParsedBillItem(BaseModel):
    productName: str
    brand: str | None = None
    packSize: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unitPrice: float | None = None
    totalPrice: float | None = None
    barcode: str | None = None
    category: str | None = None
    confidence: float
    needsReview: bool
    sourceText: str

class ParsedBill(BaseModel):
    items: list[ParsedBillItem]

api_key = os.getenv("GEMINI_API_KEY")

system_instruction = """
You are a highly accurate bill parser for an Indian grocery shop app.
Extract individual purchasable products from OCR text.
Return a JSON object containing an 'items' array of objects matching this exact schema:
{
  "items": [
    {
      "productName": "string",
      "brand": "string | null",
      "packSize": "string | null",
      "quantity": "number | null",
      "unit": "string | null",
      "unitPrice": "number | null",
      "totalPrice": "number | null",
      "barcode": "string | null",
      "category": "string | null",
      "confidence": "number (0.0 to 1.0)",
      "needsReview": "boolean",
      "sourceText": "string"
    }
  ]
}

CRITICAL RULES:
1. Units (kg, g, L, ml, pcs, packet, bottle) must NOT become part of productName.
2. "2 kg rice" -> productName: Rice, quantity: 2, unit: kg, packSize: null
3. "10 packets Parle G biscuits" -> productName: Parle G biscuits, quantity: 10, unit: packet
4. "20 bottles water 1L" -> productName: Water, quantity: 20, unit: bottle, packSize: 1 L
5. "Aashirvaad Atta 5kg 10" -> productName: Aashirvaad Atta, packSize: 5 kg, quantity: 10, unit: packet.
6. "Rice 25 kg" -> Is it 25 kg of loose rice or one 25kg bag? Ambiguous. Set needsReview = true, confidence = 0.6. Do not guess.
7. "Q Kg Rice" -> Unclear OCR. Set quantity = null, unit = null, needsReview = true, confidence = 0.4.
8. Ignore GST lines, subtotal, invoice info, thanking text. Do not invent products.
9. "2.5 kg potato" -> quantity: 2.5 (preserve decimals).
10. Prices ("10 Rs 100") must be separated into unitPrice/totalPrice. Do not confuse price with quantity.
"""

def generate_with_fallback(prompt: str, instruction: str):
    # Fetch dynamically so it always uses the current env var in cloud
    current_key = os.getenv("GEMINI_API_KEY")
    if not current_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set.")
        
    client = genai.Client(api_key=current_key)
    models = ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-2.5-flash', 'gemini-flash-latest']
    
    last_error = None
    for model_name in models:
        try:
            print(f"Trying model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    temperature=0.0,
                    response_mime_type="application/json"
                ),
            )
            data = json.loads(response.text)
            print(f"Success with {model_name}!")
            return data
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            last_error = e
            
    raise last_error

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/parse_bill", response_model=ParsedBill)
async def parse_bill(request: ParseBillRequest):
    try:
        data = generate_with_fallback(f"Parse this bill OCR text:\n\n{request.ocrText}", system_instruction)
        return ParsedBill(**data)
    except HTTPException:
        raise
    except Exception as e:
        print(f"All models failed for bill parsing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ParseVoiceStockRequest(BaseModel):
    text: str
    language: str

voice_system_instruction = """
You are a highly accurate natural language parser for an Indian grocery shop app.
Extract stock addition intentions from spoken text.
Return a JSON object containing an 'items' array of objects matching this exact schema:
{
  "items": [
    {
      "productName": "string",
      "brand": "string | null",
      "packSize": "string | null",
      "quantity": "number | null",
      "unit": "string | null",
      "barcode": "string | null",
      "category": "string | null",
      "confidence": "number (0.0 to 1.0)",
      "needsReview": "boolean",
      "sourceText": "string (the original text phrase)"
    }
  ]
}

CRITICAL RULES:
1. NEVER invent information. If brand, pack size, or barcode is missing, set to null.
2. If quantity is missing or ambiguous (e.g. "Add some rice"), set quantity = null and needsReview = true. DO NOT assume quantity = 1.
3. Understand pack sizes: "10 bottles of 1 litre oil" -> quantity: 10, unit: bottle, packSize: "1 l", productName: "Oil". Do NOT mix pack size and purchase quantity.
4. Normalize units: kilos -> kg, lit -> l, packets -> packet, pcs -> pc, etc.
5. Preserve meaningful numbers in product names like "7UP" or "5 Star". DO NOT remove them or confuse them with quantities.
6. Support multilingual input (English, Kannada, Hindi) and code-switching ("10 kilo rice add maadi"). Map them to English JSON fields.
7. If intent is REMOVAL or NON-INVENTORY (e.g., "What are my sales", "Remove 5 kg rice"), return needsReview = true with quantity = null or return an empty array if completely irrelevant. Do NOT silently convert removal into addition.
"""

@app.post("/parse_voice_stock", response_model=ParsedBill)
async def parse_voice_stock(request: ParseVoiceStockRequest):
    try:
        prompt = f"Language: {request.language}\n\nParse this voice request for adding stock:\n\n\"{request.text}\""
        data = generate_with_fallback(prompt, voice_system_instruction)
        return ParsedBill(**data)
    except HTTPException:
        raise
    except Exception as e:
        print(f"All models failed for voice parsing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
