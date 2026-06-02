#!/usr/bin/env python
# -*- coding: utf-8 -*-


from celery_app import celery_app

@celery_app.task(name="build_documents")
def build_documents(document_ids: list[UUID]) -> None:
    pass
    