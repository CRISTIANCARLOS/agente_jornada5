from microjornada5 import tools
import json

def test():
    res = tools.get_simultaneidade('5064', '2025-01-01', '2025-12-31')
    print(json.dumps(res, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test()
