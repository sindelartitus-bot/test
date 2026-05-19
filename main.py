import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import datetime
import requests
import akshare as ak
import yfinance as yf
import google.generativeai as genai

# ==========================================
# 1. 数据抓取模块
# ==========================================
def fetch_market_data():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raw_data = f"【采集时间】: {now_str}\n"
    
    try:
        chip_etf = ak.fund_etf_spot_em()
        target_etf = chip_etf[chip_etf['代码'] == '159995'].iloc[0]
        raw_data += f"[A股] 华夏芯片ETF(159995): 最新价 {target_etf['最新价']}, 涨跌幅 {target_etf['涨跌幅']}%\n"
        
        sox = yf.Ticker("^SOX").history(period="1d").iloc[-1]
        mu = yf.Ticker("MU").history(period="1d").iloc[-1]
        sox_pct = ((sox['Close'] - sox['Open']) / sox['Open']) * 100
        mu_pct = ((mu['Close'] - mu['Open']) / mu['Open']) * 100
        
        raw_data += f"[美股] 费城半导体(SOX): 收盘 {sox['Close']:.2f}, 涨跌幅 {sox_pct:.2f}%\n"
        raw_data += f"[美股] 美光科技(MU): 收盘 {mu['Close']:.2f}, 涨跌幅 {mu_pct:.2f}%\n"
    except Exception as e:
        raw_data += f"[数据抓取异常]: {str(e)}\n"
        
    return raw_data

# ==========================================
# 2. Gemini AI 推理模块
# ==========================================
def generate_ai_report(raw_data, period_name):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return raw_data + "\n\n[警告] 未获取到 GEMINI_API_KEY，直接输出原始数据。"
        
    genai.configure(api_key=api_key)
    # 使用基础模型即可胜任该任务
    model = genai.GenerativeModel('gemini-3.1-flash-lite')
    
    prompt = f"""
    你是一位冷酷、纪律严明的量化交易员。请根据以下最新的半导体市场高频数据，撰写一份无废话的【{period_name}】简报。
    【市场数据】
    {raw_data}
    【撰写纪律】
    1. 必须客观分析海外情绪（费半、美光）对 A 股芯片ETF（159995）的潜在传导影响。
    2. 必须在文末附上【冷酷告诫】：当前持有策略为右侧交易，盘中若跌破 2.35 支撑位必须无条件清仓，未跌破则严禁盲目动仓。
    3. 语气严厉、专业，拒绝任何模棱两可的情绪化表达。
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"[AI 生成失败]: {str(e)}\n\n原始数据:\n{raw_data}"

# ==========================================
# 3. 邮箱推送模块 (使用统一变量名)
# ==========================================
def send_email_notification(title, content):
    sender = os.environ.get("SENDER_EMAIL")
    password = os.environ.get("SENDER_AUTH_CODE")
    receiver = os.environ.get("RECEIVEREMAIL")
    smtp_server = "smtp.163.com" # 如果是126邮箱请改为 smtp.126.com

    if not all([sender, password, receiver]):
        print("未完全配置邮箱 Secrets，跳过发送")
        return

    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = Header("冷酷的AI特工", 'utf-8')
    message['To'] = Header("主理人", 'utf-8')
    message['Subject'] = Header(title, 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp_server, 465)
        server.login(sender, password)
        server.sendmail(sender, [receiver], message.as_string())
        print("邮件推送成功！")
        server.quit()
    except Exception as e:
        print(f"邮件推送失败: {str(e)}")

# ==========================================
# 4. 主执行入口
# ==========================================
if __name__ == "__main__":
    utc_hour = datetime.datetime.utcnow().hour
    period_name = "早盘风向标" if utc_hour < 4 else "盘后复盘大盘点"
    
    raw_market_data = fetch_market_data()
    print("抓取到的原始数据:\n", raw_market_data)
    
    final_report = generate_ai_report(raw_market_data, period_name)
    print("\n生成的 AI 报告:\n", final_report)
    
    title = f"【AI研报】芯片ETF {period_name}"
    send_email_notification(title, final_report)