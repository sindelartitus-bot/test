import os
import sys
import datetime
import akshare as ak
import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import google.generativeai as genai

# ==========================================
# 0. 全局配置 (通过云端环境变量安全注入)
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

SMTP_SERVER = "smtp.163.com"
SMTP_PORT = 465
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_AUTH_CODE = os.environ.get("SENDER_AUTH_CODE")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

# ==========================================
# 1. 核心数据抓取模块 (含成分股)
# ==========================================
def fetch_market_data():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_data = f"【基本面数据采集时间】: {now_str}\n\n"
    
    target_stock_codes = [
        "688041", "688008", "603986", "688256", "002371", 
        "688981", "688012", "688072", "688521", "603501", 
        "600584", "002156", "688120", "600703", "002049", 
        "300223", "300661", "300782", "688126", "600460"
    ]
    
    try:
        chip_etf = ak.fund_etf_spot_em()
        target_etf = chip_etf[chip_etf['代码'] == '159995'].iloc[0]
        report_data += f"--- A股芯片ETF表现 ---\n"
        report_data += f"华夏芯片ETF(159995): 当前价 {target_etf['最新价']}, 涨跌幅 {target_etf['涨跌幅']}%\n\n"
        
        stock_data = ak.stock_zh_a_spot_em()
        filtered_stocks = stock_data[stock_data['代码'].isin(target_stock_codes)]
        filtered_stocks = filtered_stocks.sort_values(by="涨跌幅", ascending=False)
        
        report_data += f"--- 核心成分股实时表现 (按涨跌幅排序) ---\n"
        for _, row in filtered_stocks.iterrows():
            report_data += f"{row['名称']}({row['代码']}): {row['最新价']}元, 涨幅 {row['涨跌幅']}%\n"
            
        sox = yf.Ticker("^SOX").history(period="1d").iloc[-1]
        mu = yf.Ticker("MU").history(period="1d").iloc[-1]
        
        sox_pct = ((sox['Close'] - sox['Open']) / sox['Open']) * 100
        mu_pct = ((mu['Close'] - mu['Open']) / mu['Open']) * 100
        
        report_data += f"\n--- 海外美股及映射表现 ---\n"
        report_data += f"费城半导体指数(SOX): 收盘价 {sox['Close']:.2f}, 涨跌幅 {sox_pct:.2f}%\n"
        report_data += f"美光科技(MU,存储风向标): 收盘价 {mu['Close']:.2f}, 涨跌幅 {mu_pct:.2f}%\n"
        
    except Exception as e:
        report_data += f"\n[数据抓取异常]: {str(e)}\n"
        
    return report_data

# ==========================================
# 2. Gemini API 推理模块
# ==========================================
def generate_ai_report(market_context, time_period):
    prompt = f"""
    你是一位资深的电子半导体产业研究员。请根据以下我为你抓取的最新国内外半导体市场高频数据，撰写一份结构严谨、无废话的【{time_period}】简报。

    【采集到的市场数据】
    {market_context}

    【撰写要求】
    1. 如果是【早盘分析】：分析隔夜美股对今天A股芯片ETF的开盘情绪传导。
    2. 如果是【盘后总结】：结合海外数据判断当前产业周期，给出一句话风险告诫。
    3. 核心个股异动分析：指出当天的领涨龙头和领跌拖累项，并简述它们代表的细分赛道（如算力、设备、存储、封测）。
    4. 风格要求：专业、客观、严厉，多用专业术语，严禁废话。
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini 报告生成失败: {str(e)}"

# ==========================================
# 3. 邮箱推送模块
# ==========================================
def send_email(title, content):
    html_content = f"""
    <h3>{title}</h3>
    <pre style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; white-space: pre-wrap; line-height: 1.5;">
{content}
    </pre>
    <p style="color: #888; font-size: 12px;"><i>本报告由云端 Gemini AI 自动生成并推送</i></p>
    """
    
    message = MIMEText(html_content, 'html', 'utf-8')
    message['From'] = Header(f"云端交易助理 <{SENDER_EMAIL}>", 'utf-8')
    message['To'] = Header(RECEIVER_EMAIL, 'utf-8')
    message['Subject'] = Header(title, 'utf-8')

    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SENDER_EMAIL, SENDER_AUTH_CODE)
        server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], message.as_string())
        server.quit()
        print(f"邮件成功发送至 {RECEIVER_EMAIL}！")
    except Exception as e:
        print(f"邮件发送失败: {str(e)}")

# ==========================================
# 4. 云端指令入口 (接收外部参数判断早晚)
# ==========================================
if __name__ == "__main__":
    job_type = sys.argv[1] if len(sys.argv) > 1 else "morning"

    if job_type == "morning":
        print("启动云端早盘分析...")
        raw_data = fetch_market_data()
        report = generate_ai_report(raw_data, "早盘开盘风向标（08:45）")
        send_email("🌤️ 盘前风向标 (云端发送)", report)
    elif job_type == "evening":
        print("启动云端盘后分析...")
        raw_data = fetch_market_data()
        report = generate_ai_report(raw_data, "盘后复盘大盘点（16:00）")
        send_email("🌙 盘后大总结 (云端发送)", report)