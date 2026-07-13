import type { Locale } from "@/lib/i18n";

const dictionaries = {
  "en-US": {
    metadata: {
      title: "Ledgerly — US Equity Research",
      description: "Traceable company, filing, financial, and valuation research.",
    },
    brand: "US Equity Research",
    language: "Language",
    nav: ["Company", "Filings", "Financials", "Valuation"],
    hero: {
      eyebrow: "Research workspace for individual investors",
      title: "See the business behind the ticker.",
      description:
        "Map where a company sits in its value chain, read the filings that matter, and put price and P/E into context — with evidence attached.",
      primaryAction: "Open company research",
      secondaryAction: "Upload a filing",
    },
    coverage: "NYSE · NASDAQ · SEC EDGAR",
    frame: {
      kicker: "Research frame / 01",
      title: "One company. Four connected views.",
      status: "Engineering baseline ready",
      items: [
        ["Business", "Revenue engines and core industry"],
        ["Value chain", "Upstream, midstream, downstream"],
        ["Financials", "Margins, cash flow, and trend breaks"],
        ["Valuation", "Price, EPS, trailing and forward P/E"],
      ],
    },
    evidence: {
      label: "Evidence layer",
      title: "Every conclusion stays connected to its source.",
      description:
        "Upload a company filing or let the research agent retrieve 10-K and 10-Q reports. Processing status and citations remain visible throughout the workflow.",
      source: "Primary sources",
      sourceValue: "10-K · 10-Q · XBRL",
      language: "Answer language",
      languageValue: "English · 简体中文",
    },
  },
  "zh-CN": {
    metadata: {
      title: "Ledgerly — 美股投研知识库",
      description: "有据可查的公司、财报、财务与估值研究。",
    },
    brand: "美股投研知识库",
    language: "语言",
    nav: ["公司", "财报", "财务", "估值"],
    hero: {
      eyebrow: "为散户打造的研究工作台",
      title: "看懂股票代码背后的生意。",
      description:
        "定位公司在产业链中的位置，阅读真正重要的财报，并结合证据理解股价与市盈率。",
      primaryAction: "开始公司研究",
      secondaryAction: "上传公司财报",
    },
    coverage: "纽交所 · 纳斯达克 · SEC EDGAR",
    frame: {
      kicker: "研究框架 / 01",
      title: "一家公司，四个相互连接的视角。",
      status: "工程基线已就绪",
      items: [
        ["核心业务", "收入来源与核心产业"],
        ["产业链", "上游、中游与下游位置"],
        ["财务表现", "利润率、现金流与趋势变化"],
        ["估值", "股价、EPS、历史与预期市盈率"],
      ],
    },
    evidence: {
      label: "证据层",
      title: "每一个结论都能回到原始来源。",
      description:
        "手动上传公司财报，或让研究 Agent 自动获取 10-K 与 10-Q。处理状态和引用会贯穿整个研究流程。",
      source: "一手资料",
      sourceValue: "10-K · 10-Q · XBRL",
      language: "回答语言",
      languageValue: "简体中文 · English",
    },
  },
} as const;

export function getDictionary(locale: Locale) {
  return dictionaries[locale];
}
