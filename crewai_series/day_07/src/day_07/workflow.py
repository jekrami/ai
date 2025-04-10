import asyncio
import schedule
import time
from crewai.flow.flow import Flow, listen, start, or_, and_
from litellm import completion
from dotenv import load_dotenv
import os
from crew import NewsAggregatorCrew
from pydantic import BaseModel
from file_writer_crew import FileWriterCrew
import agentops
from agentops.enums import EndState

load_dotenv()

class News(BaseModel):
    news: str = ""

class NewsFlow(Flow[News]):
    model = "gpt-4o-mini"
    model_4o = "gpt-4o"

    @start()
    def generate_news_topic(self):
        response = completion(
            model=self.model_4o,
            messages=[
                {
                    "role": "user",
                    "content": """Return a topic within the ai world that is trending.  
                    This should be 1 - 4 words.""",
                },
            ],
        )

        news_topic = response["choices"][0]["message"]["content"]

        return news_topic

    @listen(generate_news_topic)
    def generate_news(self, news_topic):
        inputs = {
            'topic': news_topic
        }

        result = NewsAggregatorCrew().crew().kickoff(inputs=inputs)

        output = result.raw
        self.state.news = output

        return output

    @listen(generate_news)
    def write_news(self):
        news = self.state.news

        inputs = {
            'news': news
        }

        FileWriterCrew().crew().kickoff(inputs=inputs)

    @listen(write_news)
    def generate_best_news(self):
        news = self.state.news

        response = completion(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": f"Choose the most important news from the following and return it: {news}",
                },
            ],
        )

        important_news = response["choices"][0]["message"]["content"]
        return important_news
    
    @listen(and_(generate_news_topic, generate_news, write_news, generate_best_news))
    def logger(self, result):
        print(f"Logger: {result}")
        print("*" * 100)
        print("News Complete!")

async def run_flow():
    agentops.init(api_key=os.getenv("AGENTOPS_API_KEY"), auto_start_session=False)
    session = agentops.start_session()

    flow = NewsFlow()
    await flow.kickoff()

    session.end_session(EndState.SUCCESS.value)

async def main():
    print("Flow scheduled to run every 1 minute. Press Ctrl+C to stop.")

    while True:
        await run_flow()
        await asyncio.sleep(60)  # Wait for 1 minute

if __name__ == "__main__":
    asyncio.run(main())
