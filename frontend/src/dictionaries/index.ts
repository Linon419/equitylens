import type { Locale } from "@/lib/i18n";
import { companyPageCopy } from "@/features/company/copy";

const dictionaries = {
  "en-US": {
    metadata: {
      title: "EquityLens — US Equity Research",
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
    auth: {
      eyebrow: "Investor workspace / secure access",
      title: "Start with the source.",
      description:
        "Sign in to save companies, filings, research notes, and evidence-backed conversations.",
      google: "Continue with Google",
      privacy:
        "EquityLens stores an application session in a secure browser cookie.",
      back: "Back to research overview",
      genericError: "Sign-in could not be completed. Try again.",
      accountLinkError:
        "This email belongs to an existing EquityLens account. Complete account linking before sign-in.",
      disabledError: "This EquityLens account is disabled.",
    },
    app: {
      nav: {
        dashboard: "Dashboard",
        settings: "Settings",
        signOut: "Sign out",
        signIn: "Sign in",
      },
      loading: "Resolving your research workspace…",
      dashboard: {
        eyebrow: "Research desk / US equities",
        title: "Understand the company behind the ticker.",
        description:
          "Locate its core business, map the upstream and downstream value chain, and connect valuation context to primary-source evidence.",
        coverage: "NYSE · NASDAQ · SEC EDGAR",
        search: {
          label: "Search companies",
          placeholder: "Ticker or company name",
          loading: "Searching the US market…",
          empty: "No matching companies found.",
          error: "Company search is temporarily unavailable.",
        },
        workflow: {
          eyebrow: "Research sequence / 01—03",
          title: "Three connected views. One evidence trail.",
          items: [
            {
              number: "01",
              title: "Core business",
              description: "See what the company sells, who pays, and which activities drive revenue.",
            },
            {
              number: "02",
              title: "Value chain",
              description: "Trace suppliers, the company layer, customers, and demand dependencies.",
            },
            {
              number: "03",
              title: "Source evidence",
              description: "Keep every material claim attached to a filing section and citation.",
            },
          ],
        },
        watchlist: {
          eyebrow: "Saved research",
          title: "Watchlist",
          guest: "Sign in to build a persistent watchlist for the companies you follow.",
          signIn: "Sign in to save companies",
          loading: "Loading your watchlist…",
          empty: "No saved companies yet. Add a ticker to begin.",
          error: "Your watchlist could not be updated.",
          addLabel: "Add ticker",
          add: "Add",
          remove: "Remove",
          price: "Price",
          pe: "P/E",
          added: "Company added to your watchlist.",
          removed: "Company removed from your watchlist.",
        },
      },
      company: companyPageCopy.en,
      settings: {
        eyebrow: "Workspace preferences",
        title: "Language and account",
        language: "Interface language",
      },
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
      title: "EquityLens — 美股投研知识库",
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
    auth: {
      eyebrow: "投资者工作台 / 安全访问",
      title: "从原始资料开始研究。",
      description: "登录后保存公司、财报、研究笔记和带有证据引用的对话。",
      google: "使用 Google 继续",
      privacy: "EquityLens 使用安全浏览器 Cookie 保存应用会话。",
      back: "返回研究概览",
      genericError: "登录未完成，请重试。",
      accountLinkError: "该邮箱已属于现有 EquityLens 账户，请先完成账户绑定。",
      disabledError: "该 EquityLens 账户已停用。",
    },
    app: {
      nav: {
        dashboard: "研究台",
        settings: "设置",
        signOut: "退出登录",
        signIn: "登录",
      },
      loading: "正在载入你的研究工作台…",
      dashboard: {
        eyebrow: "美股研究台 / 个股研究",
        title: "看懂股票代码背后的公司。",
        description:
          "识别公司的核心业务，梳理上下游产业链，并把估值信息与一手财报证据连接起来。",
        coverage: "纽交所 · 纳斯达克 · SEC EDGAR",
        search: {
          label: "搜索公司",
          placeholder: "输入股票代码或公司名称",
          loading: "正在搜索美股公司…",
          empty: "没有找到匹配的公司。",
          error: "公司搜索暂时不可用。",
        },
        workflow: {
          eyebrow: "研究路径 / 01—03",
          title: "三个相连的视角，一条完整证据链。",
          items: [
            {
              number: "01",
              title: "核心业务",
              description: "了解公司卖什么、谁在付费，以及哪些业务活动创造收入。",
            },
            {
              number: "02",
              title: "产业链",
              description: "追踪供应商、公司所处层级、客户与终端需求依赖。",
            },
            {
              number: "03",
              title: "原始证据",
              description: "让每一个重要结论都连接到财报章节和具体引用。",
            },
          ],
        },
        watchlist: {
          eyebrow: "已保存研究",
          title: "自选股",
          guest: "登录后建立长期自选股列表，持续跟踪你关注的公司。",
          signIn: "登录并保存公司",
          loading: "正在载入自选股…",
          empty: "还没有保存公司，添加一个股票代码开始研究。",
          error: "自选股更新失败。",
          addLabel: "添加股票代码",
          add: "添加",
          remove: "移除",
          price: "股价",
          pe: "市盈率",
          added: "公司已加入自选股。",
          removed: "公司已从自选股移除。",
        },
      },
      company: companyPageCopy.zh,
      settings: {
        eyebrow: "工作台偏好",
        title: "语言与账户",
        language: "界面语言",
      },
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
