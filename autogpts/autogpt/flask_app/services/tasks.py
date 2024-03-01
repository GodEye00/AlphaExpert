import os
from time import sleep
from celery.exceptions import MaxRetriesExceededError
from flask import current_app

from utils import process_file, redis, read_files, formatter
# from helpers import model
from app import celery


@celery.task(bind=True)
def split_and_process(self, file_path, model_name):
    current_app.logger.info("Splitting and processing file...")
    id = self.request.id
    try:
        file_content = read_files.read_file(file_path)
        total_chunks = process_file.split_file(file_content)
        
        async_results = []
        for i, chunk in enumerate(total_chunks, start=1):
            async_result = process_message_with_model.apply_async(args=[chunk, model_name, id])
            async_results.append(async_result)

        completed_tasks = 0

        while not all(result.ready() for result in async_results):
            # Update the count of completed tasks
            newly_completed_tasks = sum(result.ready() for result in async_results)
            if newly_completed_tasks > completed_tasks:
                # Only update the state if there's new progress
                completed_tasks = newly_completed_tasks
                self.update_state(state='PROGRESS', meta={'current': completed_tasks, 'total': len(total_chunks), 'status': 'Processing'})
            sleep(1)

        successful_tasks = sum(result.successful() for result in async_results)
        success_percentage = (successful_tasks / len(async_results)) * 100

        if success_percentage >= 50:
            # Ensure save is called after progress update to prevent race condition
            save.apply_async(args=[file_path, id])
            self.update_state(state='SUCCESS', meta={'current': len(total_chunks), 'total': len(total_chunks), 'status': f'Task Completed. Percent complete: {success_percentage}'})
        else:
            current_app.logger.info(f"Not saving task due to task incompletion rate of {100-success_percentage}")
            self.update_state(state='FAILURE', meta={'status': 'Failed', 'reason': 'Less than 50% of the tasks were successful'})

    except Exception as e:
        current_app.logger.error(f"Error in split_and_process: {e}")
        self.update_state(state='FAILURE', meta={'status': 'Failed', 'reason': str(e)})





@celery.task(bind=True, max_retries=3, default_retry_delay=5)
def save(self, original_file_path, id):
    current_app.logger.info("About to save processed file to disk")
    try:
        file_content = redis.get(id)
        save_dir = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        file_name = redis.get(f"file-{id}")
        if not file_name:
            file_name = f"API-{id}"
        download_filename = f"{file_name}-{id[:5]}-Documentation"
        filename = f"{download_filename}.docx"
        file_path = os.path.join(save_dir, filename)
        formatter.format_doc(file_path, file_content)
        delete_from_cache.apply_async(args=[id])
        os.remove(original_file_path)
    except Exception as e:
        try:
            current_app.logger.exception(f"An error occurred while saving processed file. Error: {e}")
            self.retry(exc=e)
        except MaxRetriesExceededError:
            raise Exception(f"Could not save json file. Got Error: {e}")



@celery.task(bind=True, max_retries=3, default_retry_delay=5)
def process_message_with_model(self, text, model_name, task_id):
    """
    Task to process a message with a specified model.
    """
    try:
        # default_message = model.default_messages
        message = {"role": "user", "content": text }
        # conversation = default_message.copy() + [message]
        def switcher(model):
            # if model == 'gpt4':
            #     return ask_openai("gpt-4", conversation)
            # elif model == "gpt3.5":
            #     return ask_openai("gpt-3.5-turbo", conversation)
            # elif model == "anthropic":
            #     return ask_bedrock("anthropic.claude-v2", conversation)
            # else:
            #     return  "Model not supported"
            return ''

        response = switcher(model_name)
        content = response['content'] if response and 'content' in response else ''
        cached_data = redis.get(task_id)
        data = cached_data + "\n\n" + content
        redis.save(task_id, data)
        sleep(10)
        return response
    except Exception as e:
        try:
            self.retry(exc=e)
        except MaxRetriesExceededError:
            current_app.logger.exception(f"An error occurred while trying to obtain response from server. Error: {e}")


@celery.task(bind=True, max_retries=3, default_retry_delay=5)
def set_conversation_to_cache(self, id, message):
    try:
        return redis.save(id, message)
    except Exception as e:
        try:
            self.retry(exc=e)
        except MaxRetriesExceededError:
            raise Exception("Max retries exceeded for task set_conversation_to_cache") from e

@celery.task(bind=True, max_retries=3, default_retry_delay=5)
def delete_from_cache(self, id):
    try:
        return redis.delete_from_cache(id)
    except Exception as e:
        try:
            self.retry(exc=e)
        except MaxRetriesExceededError:
            raise Exception("Max retries exceeded for task delete_from_cache") from e



