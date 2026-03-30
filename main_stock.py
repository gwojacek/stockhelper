from core.factory import StrategyFactory
from configs.stocks import pepco, CCC, kruk, jsw, opl, BDX, KTY, zabka, BFT, CPS, ATT, pkp, mrb, SPL, rbw, apr, vercom, \
    CDR, DNP, SNT, xtb, LBW, kghm, peo, enea, Mobruk, medalg, ALE, DAD, LMT_US, pxm, DIA, bmc, pkn, pge


def analyze(config_module):
    strategy = StrategyFactory.create(config_module.TradingConfig())
    strategy.calculate()
    strategy.display_results()


if __name__ == "__main__":
    # analyze(peo)
    # analyze(xtb)
    analyze(BFT)


