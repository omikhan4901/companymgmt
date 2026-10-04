/** Friendly names for the generated OpenAPI schema types. */
import type { components } from "./schema";

type S = components["schemas"];

export type Me = S["MeOut"];
export type CurrentWorkspace = S["CurrentWorkspace"];
export type WorkspaceRef = S["WorkspaceRef"];
export type Plan = S["PublicPlan"];
export type Workspace = S["WorkspaceOut"];
export type Member = S["MemberOut"];
export type Role = S["RoleOut"];
export type Permission = S["PermissionOut"];
export type Invite = S["InviteOut"];
export type Branch = S["BranchOut"];
export type AuditEvent = S["AuditOut"];
export type Session = S["SessionOut"];
export type Department = S["DepartmentOut"];
export type Employee = S["EmployeeOut"];
export type AttendanceRecord = S["RecordOut"];
export type AttendanceStatus = S["StatusOut"];
export type Correction = S["CorrectionOut"];
export type Timesheet = S["TimesheetOut"];
export type Present = S["PresentOut"];
export type StaffCreated = S["StaffOut"];

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface Token {
  access_token: string;
  expires_at: string;
}

export interface LoginResult {
  mfa_required: boolean;
  challenge: string | null;
  access_token: string | null;
}
export type AttendanceSettings = S["SettingsOut"];
export type GeoResult = "inside" | "outside" | "no_fix" | "no_site";
export type LeaveType = S["LeaveTypeOut"];
export type LeavePolicy = S["PolicyOut"];
export type Holiday = S["HolidayOut"];
export type LeaveBalance = S["BalanceOut"];
export type PersonBalances = S["PersonBalances"];
export type LeaveRequest = S["RequestOut"];
export type LeaveQuote = S["QuoteOut"];
export type AwayEntry = S["CalendarEntry"];
export type LeaveAdjustment = S["AdjustmentOut"];
export type PayrollSettings = S["PayrollSettingsOut"];
export type TaxTable = S["TaxTable-Output"];
export type SalaryStructure = S["StructureOut"];
export type Loan = S["LoanOut"];
export type PayRun = S["RunOut"];
export type PayRunDetail = S["RunDetail"];
export type Payslip = S["PayslipOut"];
export type PayItem = S["ItemOut"];
export type Notification = S["NotificationOut"];
export type Inbox = S["InboxOut"];
export type Project = S["ProjectOut"];
export type Task = S["TaskOut"];
export type TaskDetail = S["TaskDetail"];
export type OnboardingTemplate = S["TemplateOut"];
export type OnboardingRun = S["OnboardingRunOut"];
export type ChecklistItem = S["ChecklistItemOut"];
export type TaskComment = S["CommentOut"];
export type Announcement = S["AnnouncementOut"];
export type Receipts = S["ReceiptsOut"];
export type Doc = S["DocumentOut"];
export type DocDetail = S["DocumentDetail"];
export type DocAcks = S["AcksOut"];
export type ApprovalItem = S["ApprovalItem"];
export type ImportResult = S["ImportOut"];
export type Overview = S["OverviewOut"];
export type ReportSubscription = S["SubscriptionOut"];
export type AIStatus = S["AIStatusOut"];
export type AIAnswer = S["AnswerOut"];
export type AIMessage = S["MessageOut"];
export type AISource = S["SourceOut"];
export type AIConversation = S["ConversationOut"];
export type AIBrief = S["BriefOut"];
export type AIAllowance = S["AllowanceOut"];
export type AIAction = S["ActionOut"];
export type Automation = S["AutomationOut"];
export type AutomationInput = S["AutomationIn"];
export type AutomationRun = S["AutomationRunOut"];
export type AutomationDraft = S["DraftOut"];
export type Signals = S["SignalsOut"];
export type Signal = S["SignalOut"];
export type ShopSettings = S["ShopSettingsOut"];
export type TaxRate = S["TaxRateOut"];
export type ProductCategory = S["ProductCategoryOut"];
export type Product = S["ProductOut"];
export type DrawerSession = S["DrawerOut"];
export type Sale = S["SaleOut"];
export type SaleLine = S["LineOut"];
export type Receipt = S["SaleReceiptOut"];
export type SalesSummary = S["SummaryOut"];
export type Customer = S["CustomerOut"];
export type Statement = S["StatementOut"];
export type Expense = S["ExpenseOut"];
export type Expenses = S["ExpensesOut"];
export type ExpenseCategory = S["ExpenseCategoryOut"];
export type StockRow = S["StockOut"];
export type StockMove = S["MovementOut"];
export type Supplier = S["SupplierOut"];
export type PurchaseRow = S["PurchaseOut"];
export type StockCount = S["StockCountOut"];
export type LedgerAccount = S["AccountOut"];
export type JournalEntry = S["JournalEntryOut"];
export type BooksSettings = S["BooksSettingsOut"];
export type TrialBalance = S["TrialBalanceOut"];
export type ProfitLoss = S["ProfitLossOut"];
export type BalanceSheet = S["BalanceSheetOut"];
export type Ledger = S["LedgerOut"];
export type TaxTemplate = S["TaxTemplateOut"];
export type TaxReturn = S["TaxReturnOut"];
export type ReportRow = S["ReportRow"];
