import argparse
import os
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="RP creator — simulador local")
    parser.add_argument("--port", type=int, default=7342)
    parser.add_argument("--data", default=os.environ.get("RP_DATA_DIR", "data"))
    args = parser.parse_args()
    os.environ["RP_DATA_DIR"] = os.path.abspath(args.data)
    print(f"RP creator: http://127.0.0.1:{args.port} | dados: {os.environ['RP_DATA_DIR']}")
    uvicorn.run("rp_creator.api:app", host="127.0.0.1", port=args.port, workers=1)


if __name__ == "__main__":
    main()
