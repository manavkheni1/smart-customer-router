import gradio as gr
import requests
import pandas as pd
import os
from datetime import datetime

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
WEBHOOK_URL = "https://gratifiable-nonequably-israel.ngrok-free.dev/webhook/21c6802a-eb78-4a76-8d39-552ee0f73afa"
HISTORY_FILE = "triage_history.csv"

# ---------------------------------------------------------
# 2. THE LOGIC
# ---------------------------------------------------------
def get_history():
    """Loads history from CSV for the Gradio Dataframe."""
    if os.path.exists(HISTORY_FILE):
        try:
            return pd.read_csv(HISTORY_FILE)
        except:
            pass
    return pd.DataFrame(columns=["Timestamp", "Source", "Sentiment", "Score", "Reply"])

def analyze_ticket(source_input, review_text):
    payload = {"message": {"content": review_text, "source": source_input}}
    
    try:
        # A. Trigger n8n
        response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status() 
        data = response.json()
        
        # --- SAFETY CHECK FOR n8n IF-ELSE PATHS ---
        # Handles cases where the 'False' path returns an error or no data
        if not data or (isinstance(data, dict) and "error" in data):
            reason = data.get("error", "Criteria not met or manual review required.") if isinstance(data, dict) else "No data returned."
            warning_html = f"""
            <div style="background-color: #fff3cd; padding: 20px; border-radius: 10px; border: 1px solid #ffeeba; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                <h3 style="margin-top: 0; color: #856404;">⚠️ Analysis Bypassed</h3>
                <p style="color: #856404; font-weight: 500;">{reason}</p>
                <div style="font-size: 0.8em; color: #856404; opacity: 0.8;">The n8n workflow followed the 'False' branch.</div>
            </div>
            """
            return warning_html, "Manual review required.", get_history()
        # ------------------------------------------

        # B. Handle Batch Data (Successful path)
        incoming_results = data if isinstance(data, list) else [data]
        
        target_item = None
        new_entries = []
        search_fingerprint = review_text[:20].lower()

        for item in incoming_results:
            sentiment = item.get("sentiment_label", "Unknown")
            score = item.get("sentiment_score", "0")
            reply = item.get("suggested_response", "No response generated.")
            
            # Check for specific match to show on Dashboard
            item_content = str(item.get("summary", "")) + str(item.get("Review", ""))
            if search_fingerprint in item_content.lower():
                target_item = item
            
            new_entries.append({
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Source": item.get("source", source_input),
                "Sentiment": sentiment,
                "Score": score,
                "Reply": reply[:50] + "..." if len(reply) > 50 else reply
            })
        
        # C. Update History Table
        history_df = get_history()
        history_df = pd.concat([pd.DataFrame(new_entries), history_df], ignore_index=True)
        history_df.to_csv(HISTORY_FILE, index=False)
        
        # D. Dashboard Display (High Contrast UI)
        display_item = target_item if target_item else incoming_results[-1]
        
        sentiment = display_item.get("sentiment_label", "Unknown")
        score = display_item.get("sentiment_score", "0")
        reply = display_item.get("suggested_response", "No response.")
        final_source = display_item.get("source", source_input)
            
        emoji = "🟢" if "Positive" in sentiment else "🔴" if "Negative" in sentiment else "🟡"
        color = "green" if "Positive" in sentiment else "red" if "Negative" in sentiment else "#D4AF37"
            
        dashboard_html = f"""
        <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid #eee;">
            <h3 style="margin-top: 0; color: #111; border-bottom: 2px solid #eee; padding-bottom: 10px;">📊 Latest Analysis</h3>
            
            <div style="display: flex; justify-content: space-between; margin: 15px 0;">
                <span style="font-weight: bold; color: #333; font-size: 1.1em;">Source:</span>
                <span style="color: #666; font-size: 1.1em;">{final_source}</span>
            </div>
            
            <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                <span style="font-weight: bold; color: #333; font-size: 1.1em;">Sentiment:</span>
                <span style="color: {color}; font-weight: bold; font-size: 1.1em;">{emoji} {sentiment}</span>
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: bold; color: #333; font-size: 1.1em;">Urgency Score:</span>
                <span style="background-color: {color}; color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 1em;">
                    {score}/10
                </span>
            </div>
        </div>
        """
        
        return dashboard_html, reply, history_df

    except Exception as e:
        error_msg = f"<div style='color: red; font-weight: bold;'>❌ Error: {str(e)}</div>"
        return error_msg, "Failed to connect to n8n.", get_history()

# ---------------------------------------------------------
# 3. THE UI
# ---------------------------------------------------------
theme = gr.themes.Soft(primary_hue="indigo")

with gr.Blocks(title="AI Support Manager") as demo:
    gr.Markdown("# 🤖 Intelligent Support Manager")
    
    with gr.Row():
        # Left Side: Inputs & Examples
        with gr.Column(scale=1):
            gr.Markdown("### 📥 New Ticket")
            inp_source = gr.Dropdown(["Twitter", "Email", "Google Reviews"], label="Source", value="Email")
            inp_text = gr.Textbox(label="Message", lines=5, placeholder="Paste customer feedback here...")
            btn_submit = gr.Button("✨ Analyze Ticket", variant="primary")
            
            gr.Markdown("---")
            gr.Examples(
                examples=[
                    ["Google Reviews", "The product arrived broken and customer service won't answer."],
                    ["Email", "I just wanted to say thank you for the fast shipping!"],
                    ["Twitter", "Your website is currently down. Is there an ETA for a fix?"]
                ],
                inputs=[inp_source, inp_text],
                label="Quick Test Examples"
            )

        # Right Side: Results Dashboard
        with gr.Column(scale=1):
            gr.Markdown("### 🧠 AI Analysis")
            out_dashboard = gr.HTML(value="<div style='color: #666; font-style: italic; padding: 20px; border: 1px dashed #ccc; border-radius: 10px;'>Run analysis to see results...</div>")
            out_reply = gr.Textbox(label="📝 Drafted Response", lines=8, interactive=False)

    # Bottom: History Table
    gr.Markdown("---")
    gr.Markdown("### 🗄️ Processing History")
    out_table = gr.Dataframe(value=get_history(), interactive=False, wrap=True)

    # Connections
    btn_submit.click(
        fn=analyze_ticket,
        inputs=[inp_source, inp_text],
        outputs=[out_dashboard, out_reply, out_table]
    )

if __name__ == "__main__":
    demo.launch(theme=theme)
