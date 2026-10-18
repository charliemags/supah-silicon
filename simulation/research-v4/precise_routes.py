"""Run the same exhaustive route search with extra output digits only."""
import os
from pathlib import Path
os.environ['CRYO_HOTSPOT']=str(Path(__file__).resolve().parents[2]/'.cache/hotspot-precise')
from search import main
if __name__=='__main__':main()
