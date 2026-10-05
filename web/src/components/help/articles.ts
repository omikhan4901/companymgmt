/** The help centre's articles, in English and Bangla. Short, task-shaped, and only about
 * what the app really does. */

export interface Article {
  id: string;
  /** Where in the app it applies (for "Open" links). */
  href?: string;
  en: { title: string; steps: string[] };
  bn: { title: string; steps: string[] };
}

export const ARTICLES: Article[] = [
  {
    id: "start",
    href: "/app",
    en: {
      title: "Getting started",
      steps: [
        "Follow the first-day checklist on the home page: company details, a branch, your team, two-step sign-in.",
        "Try sample data if you want to look around first; remove it from the same card in one click.",
        "Your workspace has its own address (Settings → Workspace). Staff sign in there with a username, no email needed.",
        "Invite people by email (Team), add staff accounts with a username, or share a join link or QR code (Team → Join links).",
      ],
    },
    bn: {
      title: "শুরু করা",
      steps: [
        "হোম পেজের প্রথম দিনের চেকলিস্ট অনুসরণ করুন: কোম্পানির তথ্য, একটি শাখা, আপনার দল, দুই ধাপের সাইন-ইন।",
        "আগে ঘুরে দেখতে চাইলে নমুনা ডেটা নিন; একই কার্ড থেকে এক ক্লিকে সরান।",
        "আপনার ওয়ার্কস্পেসের নিজস্ব ঠিকানা আছে (সেটিংস → ওয়ার্কস্পেস)। স্টাফরা সেখানে ইউজারনেম দিয়ে সাইন ইন করেন, ইমেইল লাগে না।",
        "ইমেইলে আমন্ত্রণ জানান (টিম), ইউজারনেম দিয়ে স্টাফ অ্যাকাউন্ট যোগ করুন, বা জয়েন লিংক বা QR কোড শেয়ার করুন (টিম → জয়েন লিংক)।",
      ],
    },
  },
  {
    id: "attendance",
    href: "/app/attendance",
    en: {
      title: "Clocking in and out",
      steps: [
        "Open Attendance and tap Clock in when you start, Clock out when you finish.",
        "If your workspace uses the location check, your phone shares its position at that moment only, and you must be near your branch.",
        "Forgot to clock out? Ask for a time fix from your records; your manager approves it in Approvals.",
        "Managers see today's board, all records and a timesheet; lateness follows Settings → Branches → working day start.",
      ],
    },
    bn: {
      title: "ক্লক-ইন ও ক্লক-আউট",
      steps: [
        "উপস্থিতি খুলে কাজ শুরুর সময় ক্লক-ইন, শেষে ক্লক-আউট চাপুন।",
        "ওয়ার্কস্পেসে লোকেশন যাচাই চালু থাকলে শুধু ওই মুহূর্তে আপনার ফোনের অবস্থান নেওয়া হয়, এবং আপনাকে শাখার কাছে থাকতে হবে।",
        "ক্লক-আউট করতে ভুলে গেছেন? রেকর্ড থেকে সময় সংশোধন চান; ম্যানেজার অনুমোদন পাতায় অনুমোদন দেবেন।",
        "ম্যানেজাররা আজকের বোর্ড, সব রেকর্ড ও টাইমশিট দেখেন; দেরি গণনা সেটিংস → শাখা → কাজ শুরুর সময় অনুযায়ী।",
      ],
    },
  },
  {
    id: "leave",
    href: "/app/leave",
    en: {
      title: "Leave",
      steps: [
        "Leave → Ask for leave: choose the type and days; the number of working days is counted for you.",
        "Your manager approves or turns it down in Approvals; you're notified either way.",
        "Balances show what's left this year. Admins set leave types, yearly days and holidays in Leave → Settings.",
      ],
    },
    bn: {
      title: "ছুটি",
      steps: [
        "ছুটি → ছুটি চান: ধরন ও দিন বেছে নিন; কর্মদিবস নিজে থেকে গোনা হয়।",
        "ম্যানেজার অনুমোদন পাতায় অনুমোদন দেন বা ফেরান; দুই ক্ষেত্রেই আপনাকে জানানো হয়।",
        "ব্যালান্সে এ বছরের বাকি ছুটি দেখা যায়। অ্যাডমিন ছুটি → সেটিংস থেকে ধরন, বছরের দিন ও ছুটির দিন ঠিক করেন।",
      ],
    },
  },
  {
    id: "payroll",
    href: "/app/payroll",
    en: {
      title: "Running payroll",
      steps: [
        "Set each person's salary and allowances in Payroll → Salaries.",
        "Start a pay run for the month, check every line, then submit and finalise it.",
        "Payslips (English or Bangla PDFs) are ready for each person under My payslips.",
        "Tax deduction uses the table in Payroll → Settings: have your tax adviser check it before switching it on.",
      ],
    },
    bn: {
      title: "বেতন চালানো",
      steps: [
        "বেতন → বেতন কাঠামো থেকে প্রত্যেকের বেতন ও ভাতা ঠিক করুন।",
        "মাসের পে রান শুরু করুন, প্রতিটি লাইন দেখুন, তারপর জমা দিয়ে চূড়ান্ত করুন।",
        "প্রত্যেকের পে-স্লিপ (ইংরেজি বা বাংলা PDF) আমার পে-স্লিপে পাওয়া যায়।",
        "কর কর্তন বেতন → সেটিংসের সারণি অনুযায়ী হয়: চালুর আগে কর উপদেষ্টাকে দিয়ে যাচাই করান।",
      ],
    },
  },
  {
    id: "till",
    href: "/app/pos",
    en: {
      title: "Selling at the till",
      steps: [
        "Open the cash drawer with the cash in it, then add items by tapping or searching and take payment.",
        "If the internet drops, sales are kept on the device and sent when it's back.",
        "Close the drawer at the end of the day: count the cash and see any difference.",
        "Shared device? A manager registers it in Sales → Tills; cashiers set a PIN in Account and unlock it at /till.",
        "Taxes and receipt text are set in Sales → Taxes and receipts by you or your accountant.",
      ],
    },
    bn: {
      title: "টিলে বিক্রি",
      steps: [
        "ভেতরের নগদসহ ক্যাশ ড্রয়ার খুলুন, তারপর ট্যাপ বা খুঁজে পণ্য যোগ করে টাকা নিন।",
        "ইন্টারনেট চলে গেলে বিক্রি ডিভাইসে থাকে, ফিরে এলে পাঠানো হয়।",
        "দিনের শেষে ড্রয়ার বন্ধ করুন: নগদ গুনুন এবং পার্থক্য দেখুন।",
        "শেয়ার করা ডিভাইস? ম্যানেজার বিক্রি → টিল থেকে নিবন্ধন করেন; ক্যাশিয়াররা অ্যাকাউন্টে PIN দিয়ে /till-এ খোলেন।",
        "কর ও রসিদের লেখা আপনি বা আপনার হিসাবরক্ষক বিক্রি → কর ও রসিদ থেকে ঠিক করেন।",
      ],
    },
  },
  {
    id: "dues",
    href: "/app/customers",
    en: {
      title: "Customers and dues (baki)",
      steps: [
        "Sell on account by choosing the customer at the till; it's added to what they owe.",
        "Record payments and adjustments on the customer's page; a statement shows every entry.",
        "Share a reminder by WhatsApp from the customer's page.",
      ],
    },
    bn: {
      title: "গ্রাহক ও বাকি",
      steps: [
        "টিলে গ্রাহক বেছে নিয়ে বাকিতে বিক্রি করুন; তা তার দেনায় যোগ হয়।",
        "গ্রাহকের পাতায় পরিশোধ ও সমন্বয় লিখুন; স্টেটমেন্টে প্রতিটি এন্ট্রি দেখা যায়।",
        "গ্রাহকের পাতা থেকে WhatsApp-এ মনে করিয়ে দিন।",
      ],
    },
  },
  {
    id: "books",
    href: "/app/accounting",
    en: {
      title: "Stock and the books",
      steps: [
        "Inventory: receive purchases, pay suppliers, move stock between branches and count it; low stock is flagged.",
        "Books: sales, purchases, expenses, payments and payroll post themselves. See profit and loss, the balance sheet and the cash book.",
        "Tax returns: your accountant builds a template once; fill it for any period.",
        "Lock a period when it's closed so nothing changes it.",
      ],
    },
    bn: {
      title: "মজুদ ও হিসাব",
      steps: [
        "মজুদ: ক্রয় গ্রহণ, সরবরাহকারীকে পরিশোধ, শাখার মধ্যে স্থানান্তর ও গণনা; কম মজুদ চিহ্নিত হয়।",
        "হিসাব: বিক্রি, ক্রয়, খরচ, পরিশোধ ও বেতন নিজে থেকে পোস্ট হয়। লাভ-ক্ষতি, ব্যালান্স শিট ও নগদ খাতা দেখুন।",
        "কর রিটার্ন: হিসাবরক্ষক একবার টেমপ্লেট বানান; যেকোনো সময়ের জন্য পূরণ করুন।",
        "সময়কাল বন্ধ হলে লক করুন যাতে কিছু না বদলায়।",
      ],
    },
  },
  {
    id: "work",
    href: "/app/tasks",
    en: {
      title: "Tasks, announcements and documents",
      steps: [
        "Tasks: projects with a board; assign, set due dates, comment. My work shows what's yours.",
        "Announcements: post to everyone or a department and see who has read it.",
        "Documents: publish policies and ask people to confirm they've read them.",
      ],
    },
    bn: {
      title: "কাজ, ঘোষণা ও ডকুমেন্ট",
      steps: [
        "কাজ: বোর্ডসহ প্রকল্প; দায়িত্ব দিন, শেষ তারিখ দিন, মন্তব্য করুন। আমার কাজে আপনারগুলো দেখা যায়।",
        "ঘোষণা: সবাইকে বা একটি বিভাগকে পোস্ট করুন এবং কে পড়েছেন দেখুন।",
        "ডকুমেন্ট: নীতি প্রকাশ করুন এবং পড়েছেন কিনা নিশ্চিত করতে বলুন।",
      ],
    },
  },
  {
    id: "ai",
    href: "/app/ask",
    en: {
      title: "The AI assistant",
      steps: [
        "The owner switches it on in Settings → AI assistant; admins choose what it helps with.",
        "Ask in plain words. Answers link to where each fact came from.",
        "It only sees what you may see. If it offers to change something, nothing happens until you press Confirm.",
      ],
    },
    bn: {
      title: "AI সহকারী",
      steps: [
        "মালিক সেটিংস → AI সহকারী থেকে চালু করেন; অ্যাডমিন বেছে নেন কোন কাজে সাহায্য করবে।",
        "সহজ ভাষায় জিজ্ঞেস করুন। উত্তরে প্রতিটি তথ্যের উৎসের লিংক থাকে।",
        "আপনি যা দেখতে পারেন শুধু তা-ই দেখে। কিছু বদলানোর প্রস্তাব দিলে আপনি নিশ্চিত না করা পর্যন্ত কিছু হয় না।",
      ],
    },
  },
  {
    id: "security",
    href: "/app/account",
    en: {
      title: "Keeping your account safe",
      steps: [
        "Add a passkey or two-step sign-in in Account.",
        "See every signed-in device in Account → Sessions and sign out the ones you don't recognise.",
        "We email you when your account is opened from a new device.",
      ],
    },
    bn: {
      title: "অ্যাকাউন্ট নিরাপদ রাখা",
      steps: [
        "অ্যাকাউন্ট থেকে পাসকী বা দুই ধাপের সাইন-ইন যোগ করুন।",
        "অ্যাকাউন্ট → সেশনে সাইন-ইন করা সব ডিভাইস দেখুন এবং অচেনাগুলো থেকে সাইন আউট করুন।",
        "নতুন ডিভাইস থেকে অ্যাকাউন্ট খোলা হলে আমরা ইমেইল করি।",
      ],
    },
  },
  {
    id: "data",
    href: "/app/settings",
    en: {
      title: "Exporting and deleting data",
      steps: [
        "Download what a workspace holds about you from Account.",
        "Owners export the whole workspace from Settings → Data.",
        "Deleting a workspace can be undone by its owner for 30 days; then it's erased and you get a signed certificate.",
      ],
    },
    bn: {
      title: "ডেটা রপ্তানি ও মোছা",
      steps: [
        "অ্যাকাউন্ট থেকে ওয়ার্কস্পেসে আপনার সম্পর্কে যা আছে ডাউনলোড করুন।",
        "মালিক সেটিংস → ডেটা থেকে পুরো ওয়ার্কস্পেস রপ্তানি করেন।",
        "ওয়ার্কস্পেস মোছা মালিক ৩০ দিন ফেরাতে পারেন; তারপর মুছে ফেলা হয় এবং স্বাক্ষরিত সনদ পাঠানো হয়।",
      ],
    },
  },
  {
    id: "developers",
    href: "/app/settings",
    en: {
      title: "Connecting other systems",
      steps: [
        "Settings → Developers: make API keys with only the permissions an integration needs.",
        "Webhooks tell your systems when people join or leave, leave is approved, or a sale is made; every delivery is signed.",
        "Enterprise: company sign-in (Google, Microsoft, Okta) and automatic provisioning in Settings → Security.",
      ],
    },
    bn: {
      title: "অন্য সিস্টেম যুক্ত করা",
      steps: [
        "সেটিংস → ডেভেলপার: শুধু প্রয়োজনীয় অনুমতি দিয়ে API কী তৈরি করুন।",
        "কেউ যোগ দিলে বা চলে গেলে, ছুটি অনুমোদন হলে বা বিক্রি হলে ওয়েবহুক আপনার সিস্টেমকে জানায়; প্রতিটি ডেলিভারি স্বাক্ষরিত।",
        "এন্টারপ্রাইজ: সেটিংস → নিরাপত্তা থেকে কোম্পানি সাইন-ইন (Google, Microsoft, Okta) ও স্বয়ংক্রিয় প্রভিশনিং।",
      ],
    },
  },
];

/** Articles whose title or steps contain every word of the query (any language). */
export function searchArticles(query: string, lang: "en" | "bn"): Article[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return ARTICLES;
  return ARTICLES.filter((a) => {
    const text = [a[lang].title, ...a[lang].steps, a.en.title, ...a.en.steps].join(" ").toLowerCase();
    return words.every((w) => text.includes(w));
  });
}
