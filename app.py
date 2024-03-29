# Import the required modules
import argparse
import logging
import uvicorn
from fastapi import FastAPI

from routers import auth, chats, statistics, stops, algorithm, bus
from fastapi.middleware.cors import CORSMiddleware


# Create the FastAPI app
app = FastAPI()

app.include_router(algorithm.router)
app.include_router(auth.router)
app.include_router(bus.router)
app.include_router(chats.router)
app.include_router(statistics.router)
app.include_router(stops.router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--port",
        dest="port",
        type=int,
        default=8000,
        help="Port to run the application on"
    )
    args = parser.parse_args()

    logging.basicConfig(filename='app.log', level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=args.port)
